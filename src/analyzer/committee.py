from __future__ import annotations

import json
import os
import time
from collections import Counter
from typing import Any, Callable

from src.analyzer.committee_prompt import (
    build_growth_analyst_prompt,
    build_macro_strategist_prompt,
    build_pm_prompt,
    build_risk_manager_prompt,
    build_value_skeptic_prompt,
)
from src.types import TickerAnalysis
from src.utils.cost_tracker import calculate_response_cost
from src.utils.model_config import (
    CommitteeConfig,
    load_committee_config,
    load_model_profile,
    response_temperature_kwargs,
)
from src.utils.pipeline_logging import record_pipeline_event


COMMITTEE_ROLES = ("growth_analyst", "value_skeptic", "risk_manager", "macro_strategist", "pm")
PRE_PM_ROLES = ("growth_analyst", "value_skeptic", "risk_manager", "macro_strategist")
DEEP_REVIEW_ROLES = ("risk_manager", "macro_strategist")

_RATE_LIMIT_MAX_ATTEMPTS = 4
_RATE_LIMIT_BASE_BACKOFF_SEC = 3.0
_RATE_LIMIT_MAX_BACKOFF_SEC = 30.0

_ROLE_PROMPT_BUILDERS: dict[str, Callable[..., dict[str, Any]]] = {
    "growth_analyst": build_growth_analyst_prompt,
    "value_skeptic": build_value_skeptic_prompt,
    "risk_manager": build_risk_manager_prompt,
    "macro_strategist": build_macro_strategist_prompt,
    "pm": build_pm_prompt,
}

_STANCE_TO_ACTION = {
    "strong_buy": "buy",
    "buy": "buy",
    "watch": "watch",
    "reduce": "avoid",
    "avoid": "avoid",
}
_ALLOWED_STANCES = set(_STANCE_TO_ACTION)
_STANCE_ALIASES = ("stance", "recommendation", "action", "vote")
_SUMMARY_ALIASES = ("summary", "rationale", "thesis", "reasoning", "conclusion")
_CONFIDENCE_ALIASES = ("confidence", "confidence_score", "pm_confidence")
_STRONG_OBJECTION_ALIASES = ("strong_objection", "objection", "strongly_object", "oppose")


def default_committee_analysis() -> dict[str, Any]:
    return {
        "status": "economy_only",
        "agreement_status": "aligned",
        "deep_review_triggered": False,
        "deep_review_reasons": [],
        "roles": {},
    }


def committee_stance_to_action(stance: str | None) -> str:
    normalized = str(stance or "").strip().lower()
    return _STANCE_TO_ACTION.get(normalized, "watch")


def should_trigger_deep_committee_review(committee_payload: dict[str, Any] | None, pm_threshold: int) -> dict[str, Any]:
    if not isinstance(committee_payload, dict):
        return _deep_review_metadata(False, ["invalid_committee_payload"], None, pm_threshold)

    confidence = committee_payload.get("pm_confidence")
    try:
        pm_confidence = float(confidence)
    except (TypeError, ValueError):
        return _deep_review_metadata(False, ["invalid_pm_confidence"], confidence, pm_threshold)

    reason_codes: list[str] = []
    if pm_confidence < pm_threshold:
        reason_codes.append("pm_low_confidence")
    if bool(committee_payload.get("risk_manager", {}).get("strong_objection")):
        reason_codes.append("risk_strong_objection")
    if bool(committee_payload.get("macro_strategist", {}).get("strong_objection")):
        reason_codes.append("macro_strong_objection")
    return _deep_review_metadata(bool(reason_codes), reason_codes, pm_confidence, pm_threshold)


def run_committee_analysis(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    committee_config: CommitteeConfig | None = None,
    path: str = "config/models.yaml",
    run_role: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    committee_config = committee_config or load_committee_config(path)
    role_runner = run_role or _default_committee_role_runner

    roles: dict[str, dict[str, Any]] = {}

    economy_roles = _run_role_batch(
        analysis,
        roles=PRE_PM_ROLES,
        profile_name=committee_config.economy_model,
        round_name="economy",
        max_summary_sentences_per_role=committee_config.max_summary_sentences_per_role,
        max_summary_sentences_for_pm=committee_config.max_summary_sentences_for_pm,
        role_runner=role_runner,
    )
    roles.update(economy_roles)

    pm_economy_prompt = _build_role_prompt(
        "pm",
        analysis,
        round_name="economy",
        profile_name=committee_config.economy_model,
        max_summary_sentences=committee_config.max_summary_sentences_for_pm,
        role_outputs={role: roles[role] for role in PRE_PM_ROLES},
    )
    pm_economy = _normalize_role_output(
        "pm",
        role_runner("pm", committee_config.economy_model, pm_economy_prompt),
        round_name="economy",
        profile_name=committee_config.economy_model,
        prompt=pm_economy_prompt,
    )
    roles["pm"] = pm_economy

    deep_review = should_trigger_deep_committee_review(
        {
            "pm_confidence": _coerce_float(pm_economy.get("confidence"), default=0.0),
            "risk_manager": roles["risk_manager"],
            "macro_strategist": roles["macro_strategist"],
        },
        pm_threshold=committee_config.pm_low_confidence_threshold,
    )

    if deep_review["triggered"]:
        deep_roles = _run_role_batch(
            analysis,
            roles=DEEP_REVIEW_ROLES,
            profile_name=committee_config.deep_model,
            round_name="deep",
            max_summary_sentences_per_role=committee_config.max_summary_sentences_per_role,
            max_summary_sentences_for_pm=committee_config.max_summary_sentences_for_pm,
            role_runner=role_runner,
        )
        roles.update(deep_roles)

        pm_deep_prompt = _build_role_prompt(
            "pm",
            analysis,
            round_name="deep",
            profile_name=committee_config.deep_model,
            max_summary_sentences=committee_config.max_summary_sentences_for_pm,
            role_outputs={role: roles[role] for role in PRE_PM_ROLES},
        )
        pm_deep = _normalize_role_output(
            "pm",
            role_runner("pm", committee_config.deep_model, pm_deep_prompt),
            round_name="deep",
            profile_name=committee_config.deep_model,
            prompt=pm_deep_prompt,
        )
        roles["pm"] = pm_deep

    agreement_status = derive_agreement_status(roles)
    status = "deep_reviewed" if deep_review["triggered"] else "economy_only"

    return {
        **default_committee_analysis(),
        "status": status,
        "agreement_status": agreement_status,
        "deep_review_triggered": deep_review["triggered"],
        "deep_review_reasons": deep_review["reason_codes"],
        "roles": roles,
    }


def derive_agreement_status(roles: dict[str, dict[str, Any]]) -> str:
    if not roles:
        return "aligned"
    action_buckets = [committee_stance_to_action(payload.get("stance")) for payload in roles.values()]
    counts = Counter(action_buckets)
    if len(counts) == 1:
        return "aligned"
    if len(counts) == 2:
        return "mixed"
    return "contested"


def _deep_review_metadata(
    triggered: bool,
    reason_codes: list[str],
    pm_confidence: float | None,
    pm_threshold: float | None,
) -> dict[str, Any]:
    return {
        "triggered": triggered,
        "reason_codes": reason_codes,
        "pm_confidence": pm_confidence,
        "pm_threshold": pm_threshold,
    }


def _run_role_batch(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    roles: tuple[str, ...],
    profile_name: str,
    round_name: str,
    max_summary_sentences_per_role: int,
    max_summary_sentences_for_pm: int,
    role_runner: Callable[[str, str, dict[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    for role in roles:
        prompt = _build_role_prompt(
            role,
            analysis,
            round_name=round_name,
            profile_name=profile_name,
            max_summary_sentences=max_summary_sentences_for_pm if role == "pm" else max_summary_sentences_per_role,
            role_outputs={},
        )
        outputs[role] = _normalize_role_output(
            role,
            role_runner(role, profile_name, prompt),
            round_name=round_name,
            profile_name=profile_name,
            prompt=prompt,
        )
    return outputs


def _build_role_prompt(
    role: str,
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    role_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    builder = _ROLE_PROMPT_BUILDERS[role]
    return builder(
        analysis,
        round_name=round_name,
        profile_name=profile_name,
        max_summary_sentences=max_summary_sentences,
        role_outputs=role_outputs,
    )


def _normalize_role_output(
    role: str,
    raw_output: Any,
    *,
    round_name: str,
    profile_name: str,
    prompt: dict[str, Any],
) -> dict[str, Any]:
    payload = _coerce_role_payload(raw_output)
    stance_raw = _first_present(payload, _STANCE_ALIASES)
    stance = str(stance_raw).strip().lower() if stance_raw is not None else ""
    invalid_reasons: list[str] = []
    if stance not in _ALLOWED_STANCES:
        invalid_reasons.append("invalid_stance")
        stance = "watch"
    summary = str(_first_present(payload, _SUMMARY_ALIASES, default="")).strip()
    if not summary:
        invalid_reasons.append("missing_summary")
    confidence_raw = _first_present(payload, _CONFIDENCE_ALIASES)
    if role == "pm" and confidence_raw is None:
        invalid_reasons.append("missing_confidence")
    objection_raw = _first_present(payload, _STRONG_OBJECTION_ALIASES)
    if role in {"risk_manager", "macro_strategist"} and objection_raw is None:
        invalid_reasons.append("missing_strong_objection")
    return {
        "role": role,
        "round": round_name,
        "profile": profile_name,
        "stance": stance,
        "action": committee_stance_to_action(stance),
        "confidence": _coerce_float(confidence_raw, default=0.0),
        "strong_objection": _coerce_bool(objection_raw),
        "summary": summary,
        "valid": not invalid_reasons,
        "invalid_reason": ";".join(invalid_reasons),
    }


def _default_committee_role_runner(role: str, profile_name: str, prompt: dict[str, Any]) -> dict[str, Any]:
    if not os.getenv("OPENAI_API_KEY"):
        return _committee_role_fallback(role)

    try:
        from openai import OpenAI
    except Exception:
        return _committee_role_fallback(role)

    model_profile = load_model_profile(profile_name=profile_name)
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as exc:
        record_pipeline_event(
            "analyzer",
            "warning",
            "committee_role_client_failed",
            role=role,
            model_profile=profile_name,
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
        return _committee_role_fallback(role)

    ticker = ""
    ctx = prompt.get("context") if isinstance(prompt, dict) else None
    if isinstance(ctx, dict):
        ticker_payload = ctx.get("ticker")
        if isinstance(ticker_payload, dict):
            ticker = str(ticker_payload.get("ticker", "") or "")
    cache_key = f"committee:{role}:{profile_name}:{ticker}" if ticker else f"committee:{role}:{profile_name}"

    response = None
    last_exc: Exception | None = None
    for attempt in range(1, _RATE_LIMIT_MAX_ATTEMPTS + 1):
        try:
            response = client.responses.create(
                model=model_profile.model,
                max_output_tokens=model_profile.max_output_tokens,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": str(prompt.get("system", ""))}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": str(prompt.get("user", ""))}],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": f"committee_{role}",
                        "schema": _committee_role_schema(role),
                        "strict": True,
                    }
                },
                prompt_cache_key=cache_key,
                **response_temperature_kwargs(model_profile),
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            if attempt >= _RATE_LIMIT_MAX_ATTEMPTS or not _is_rate_limit_exception(exc):
                break
            backoff = min(
                _RATE_LIMIT_BASE_BACKOFF_SEC * (2 ** (attempt - 1)),
                _RATE_LIMIT_MAX_BACKOFF_SEC,
            )
            record_pipeline_event(
                "analyzer",
                "info",
                "committee_role_rate_limited",
                role=role,
                model=model_profile.model,
                model_profile=profile_name,
                attempt=attempt,
                backoff_seconds=backoff,
                ticker=ticker,
            )
            time.sleep(backoff)

    if last_exc is not None:
        record_pipeline_event(
            "analyzer",
            "warning",
            "committee_role_request_failed",
            role=role,
            model=model_profile.model,
            model_profile=profile_name,
            error_type=type(last_exc).__name__,
            error_message=str(last_exc)[:200],
            attempts=attempt,
        )
        return _committee_role_fallback(role)

    usage_cost = calculate_response_cost(response, model_profile)
    record_pipeline_event(
        "analyzer",
        "info",
        "openai_usage_recorded",
        model=model_profile.model,
        model_profile=model_profile.name,
        module=f"committee_{role}",
        input_tokens=usage_cost.input_tokens,
        output_tokens=usage_cost.output_tokens,
        cached_input_tokens=usage_cost.cached_input_tokens,
        total_tokens=usage_cost.total_tokens,
        estimated_cost_usd=usage_cost.estimated_cost_usd,
    )

    response_text = str(getattr(response, "output_text", "") or "").strip()
    if not response_text:
        record_pipeline_event(
            "analyzer",
            "warning",
            "committee_role_response_empty",
            role=role,
            model=model_profile.model,
            model_profile=profile_name,
        )
        return _committee_role_fallback(role)

    record_pipeline_event(
        "analyzer",
        "info",
        "openai_response_validated",
        module=f"committee_{role}",
        ticker_count=1,
    )
    return response_text


def _is_rate_limit_exception(exc: BaseException) -> bool:
    if type(exc).__name__ == "RateLimitError":
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status == 429:
        return True
    message = str(exc).lower()
    return "rate limit" in message or " 429" in message or "tpm" in message


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y"}


def _committee_role_fallback(role: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stance": "watch",
        "summary": "",
    }
    if role == "pm":
        payload["confidence"] = 0.0
    if role in {"risk_manager", "macro_strategist"}:
        payload["strong_objection"] = False
    return payload


def _committee_role_schema(role: str) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "stance": {
            "type": "string",
            "enum": sorted(_ALLOWED_STANCES),
        },
        "summary": {"type": "string"},
    }
    required = ["stance", "summary"]
    if role == "pm":
        properties["confidence"] = {"type": "number"}
        required.append("confidence")
    if role in {"risk_manager", "macro_strategist"}:
        properties["strong_objection"] = {"type": "boolean"}
        required.append("strong_objection")
    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }


def _coerce_role_payload(raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, dict):
        direct = _payload_from_mapping(raw_output)
        if direct is not None:
            return direct
        for key in ("parsed", "data", "payload", "result", "response", "json"):
            nested = raw_output.get(key)
            if nested is None:
                continue
            nested_payload = _coerce_role_payload(nested)
            if nested_payload:
                return nested_payload
        for key in ("output_text", "content", "text"):
            text_payload = _payload_from_text(raw_output.get(key))
            if text_payload:
                return text_payload
        message_payload = _payload_from_message(raw_output.get("message"))
        if message_payload:
            return message_payload
        return {}
    if isinstance(raw_output, str):
        return _payload_from_text(raw_output) or {}
    return {}


def _payload_from_mapping(payload: dict[str, Any]) -> dict[str, Any] | None:
    if any(key in payload for key in (*_STANCE_ALIASES, *_SUMMARY_ALIASES, *_CONFIDENCE_ALIASES, *_STRONG_OBJECTION_ALIASES)):
        return payload
    return None


def _payload_from_message(message: Any) -> dict[str, Any] | None:
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                payload = _payload_from_text(item.get("text"))
                if payload:
                    return payload
    return None


def _payload_from_text(value: Any) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not text:
        return None
    stripped = _strip_json_fences(text)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        direct = _payload_from_mapping(parsed)
        if direct is not None:
            return direct
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidate = stripped[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            direct = _payload_from_mapping(parsed)
            if direct is not None:
                return direct
    return None


def _strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _first_present(payload: dict[str, Any], keys: tuple[str, ...], *, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload.get(key) is not None:
            return payload.get(key)
    return default
