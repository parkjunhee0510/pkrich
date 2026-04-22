from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from dataclasses import replace
from typing import Any

from src.analyzer.base import AnalysisContext, ModuleResult, StructuredLLMModule
from src.analyzer.prompts import PromptContext, PromptTemplate, get_prompt_template
from src.analyzer.validator import ResponseValidator
from src.utils.cost_tracker import calculate_response_cost
from src.utils.model_config import (
    resolve_module_batch_size,
    resolve_module_model_profile,
    response_temperature_kwargs,
    safe_input_token_budget,
)
from src.utils.pipeline_logging import record_pipeline_event
from src.utils.token_estimator import estimate_batch_tokens


_DEFAULT_LLM_BATCH_MAX_WORKERS = 4

def run_structured_llm_module(
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    *,
    prompt_template_override: PromptTemplate | None = None,
    capture_validation_details: bool = False,
) -> ModuleResult:
    if not os.getenv("OPENAI_API_KEY") or ctx.model_profile is None:
        return _build_fallback_result(module, ctx, reason="missing_openai_key")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception:
        return _build_fallback_result(module, ctx, reason="openai_client_failed")

    tickers = [item.ticker for item in ctx.watchlist]
    all_results: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {
        "batch_count": 0,
        "fallback_batches": 0,
        "missing_retry_batches": 0,
        "missing_retry_attempts": 0,
        "missing_retry_recovered_tickers": 0,
        "validation_retry_batches": 0,
        "validation_retry_attempts": 0,
        "validation_retry_recovered_tickers": 0,
        "parallel_batch_workers": 1,
    }
    if capture_validation_details:
        diagnostics["validation_details"] = {}
    validator = ResponseValidator()
    active_model_profile = resolve_module_model_profile(ctx.model_profile, module.name)
    prompt_template = prompt_template_override or get_prompt_template(
        getattr(active_model_profile, "prompt_version", "research_v1"),
        module.name,
    )
    prompt_context = PromptContext(
        run_date=ctx.run_date,
        macro_context=ctx.macro_context,
        account_size_hint=ctx.portfolio_account_size,
        model_profile=active_model_profile,
        metadata={"module_name": module.name},
    )
    retry_budget = _missing_retry_budget(ctx)
    validation_retry_budget = _validation_retry_budget(ctx)
    batches = _split_batches(module, ctx, tickers)
    diagnostics["batch_count"] = len(batches)
    diagnostics["parallel_batch_workers"] = _resolve_batch_workers(ctx, len(batches))
    for batch_result in _iter_batch_results(
        client=client,
        module=module,
        ctx=ctx,
        model_profile=active_model_profile,
        prompt_template=prompt_template,
        prompt_context=prompt_context,
        batches=batches,
        retry_budget=retry_budget,
        max_workers=diagnostics["parallel_batch_workers"],
    ):
        diagnostics["missing_retry_batches"] += batch_result.diagnostics.get("missing_retry_batches", 0)
        diagnostics["missing_retry_attempts"] += batch_result.diagnostics.get("missing_retry_attempts", 0)
        diagnostics["missing_retry_recovered_tickers"] += batch_result.diagnostics.get("missing_retry_recovered_tickers", 0)
        batch_tickers = batch_result.batch_tickers
        try:
            if batch_result.error is not None:
                raise batch_result.error
            parsed = batch_result.parsed
            missing_tickers = list(batch_result.missing_tickers)
            if missing_tickers:
                record_pipeline_event(
                    "analyzer",
                    "warning",
                    "openai_response_missing_tickers",
                    module=module.name,
                    missing_tickers=",".join(missing_tickers),
                    missing_count=len(missing_tickers),
                    batch_ticker_count=len(batch_tickers),
                )
                for ticker in missing_tickers:
                    all_results[ticker] = module.fallback_for_ticker(ticker, ctx)
                    if capture_validation_details:
                        diagnostics["validation_details"][ticker] = {
                            "warning_count": 1,
                            "counts": {"schema_violation": 1},
                            "warnings": [
                                {
                                    "category": "schema_violation",
                                    "field": "*",
                                    "message": "missing_from_batch_response",
                                }
                            ],
                        }
            for ticker in [t for t in batch_tickers if t in parsed]:
                validated = validator.validate(
                    parsed.get(ticker, {}),
                    _result_schema_for_ticker(module, ticker, ctx),
                    {
                        "raw_payload": ctx.raw_payload_by_ticker.get(ticker, {}),
                        "fallback": module.fallback_for_ticker(ticker, ctx),
                        "intermediate": ctx.intermediate_results.get(ticker, {}),
                    },
                )
                retried_validation = False
                if validation_retry_budget > 0 and _should_retry_validation(validated):
                    diagnostics["validation_retry_batches"] += 1
                    retry_validated = _retry_single_ticker_on_validation(
                        client=client,
                        module=module,
                        ctx=ctx,
                        model_profile=active_model_profile,
                        prompt_template=prompt_template,
                        prompt_context=prompt_context,
                        ticker=ticker,
                        validator=validator,
                        retry_budget=validation_retry_budget,
                        diagnostics=diagnostics,
                    )
                    if retry_validated is not None:
                        validated = retry_validated
                        retried_validation = True
                if validated.warnings:
                    counts = validated.counts
                    record_pipeline_event(
                        "analyzer",
                        "warning",
                        "openai_response_validation_failed",
                        module=module.name,
                        ticker=ticker,
                        warning_count=len(validated.warnings),
                        warning_fields=",".join(sorted({warning.field for warning in validated.warnings})),
                        warning_categories=",".join(sorted(counts.keys())),
                        schema_violation_count=counts.get("schema_violation", 0),
                        fact_warning_count=counts.get("fact_warning", 0),
                        consistency_warning_count=counts.get("consistency_warning", 0),
                        hallucination_warning_count=counts.get("hallucination_warning", 0),
                        validation_retried=retried_validation,
                    )
                if capture_validation_details:
                    diagnostics["validation_details"][ticker] = {
                        "warning_count": len(validated.warnings),
                        "counts": validated.counts,
                        "warnings": [
                            {
                                "category": warning.category,
                                "field": warning.field,
                                "message": warning.message,
                            }
                            for warning in validated.warnings
                        ],
                    }
                all_results[ticker] = validated.sanitized_response
        except Exception as exc:
            diagnostics["fallback_batches"] += 1
            record_pipeline_event(
                "analyzer",
                "warning",
                "openai_response_validation_failed",
                module=module.name,
                ticker_count=len(batch_tickers),
                error_type=type(exc).__name__,
                error_message=str(exc),
                schema_violation_count=len(batch_tickers),
            )
            for ticker in batch_tickers:
                all_results[ticker] = module.fallback_for_ticker(ticker, ctx)
                if capture_validation_details:
                    diagnostics["validation_details"][ticker] = {
                        "warning_count": 1,
                        "counts": {"schema_violation": 1},
                        "warnings": [
                            {
                                "category": "schema_violation",
                                "field": "*",
                                "message": f"{type(exc).__name__}: {exc}",
                            }
                        ],
                }

    return ModuleResult(results_by_ticker=all_results, diagnostics=diagnostics)


class _BatchRequestResult:
    def __init__(
        self,
        *,
        batch_tickers: list[str],
        parsed: dict[str, dict[str, Any]] | None = None,
        missing_tickers: list[str] | None = None,
        diagnostics: dict[str, int] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.batch_tickers = batch_tickers
        self.parsed = parsed or {}
        self.missing_tickers = missing_tickers or []
        self.diagnostics = diagnostics or {}
        self.error = error


def _iter_batch_results(
    *,
    client: Any,
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    model_profile: Any,
    prompt_template: PromptTemplate,
    prompt_context: PromptContext,
    batches: list[list[str]],
    retry_budget: int,
    max_workers: int,
):
    if max_workers <= 1 or len(batches) <= 1:
        for batch_tickers in batches:
            yield _execute_batch_request(
                client=client,
                module=module,
                ctx=ctx,
                model_profile=model_profile,
                prompt_template=prompt_template,
                prompt_context=prompt_context,
                batch_tickers=batch_tickers,
                retry_budget=retry_budget,
            )
        return

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="llm-batch") as pool:
        futures = [
            pool.submit(
                _execute_batch_request,
                client=client,
                module=module,
                ctx=ctx,
                model_profile=model_profile,
                prompt_template=prompt_template,
                prompt_context=prompt_context,
                batch_tickers=batch_tickers,
                retry_budget=retry_budget,
            )
            for batch_tickers in batches
        ]
        for future in as_completed(futures):
            yield future.result()


def _execute_batch_request(
    *,
    client: Any,
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    model_profile: Any,
    prompt_template: PromptTemplate,
    prompt_context: PromptContext,
    batch_tickers: list[str],
    retry_budget: int,
) -> _BatchRequestResult:
    local_diagnostics = {
        "missing_retry_batches": 0,
        "missing_retry_attempts": 0,
        "missing_retry_recovered_tickers": 0,
    }
    try:
        parsed = _request_structured_batch(
            client,
            module,
            ctx,
            model_profile,
            prompt_template,
            prompt_context,
            batch_tickers,
        )
        missing_tickers = [ticker for ticker in batch_tickers if ticker not in parsed]
        if missing_tickers and retry_budget > 0:
            local_diagnostics["missing_retry_batches"] += 1
            record_pipeline_event(
                "analyzer",
                "info",
                "openai_missing_ticker_retry_started",
                module=module.name,
                missing_tickers=",".join(missing_tickers),
                missing_count=len(missing_tickers),
                retry_budget=retry_budget,
            )
            remaining_tickers = list(missing_tickers)
            for attempt in range(1, retry_budget + 1):
                if not remaining_tickers:
                    break
                local_diagnostics["missing_retry_attempts"] += 1
                try:
                    retry_parsed = _request_structured_batch(
                        client,
                        module,
                        ctx,
                        model_profile,
                        prompt_template,
                        prompt_context,
                        remaining_tickers,
                    )
                except Exception as exc:
                    record_pipeline_event(
                        "analyzer",
                        "warning",
                        "openai_missing_ticker_retry_failed",
                        module=module.name,
                        missing_tickers=",".join(remaining_tickers),
                        missing_count=len(remaining_tickers),
                        retry_attempt=attempt,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                    break
                recovered_now = [ticker for ticker in remaining_tickers if ticker in retry_parsed]
                if recovered_now:
                    for ticker in recovered_now:
                        parsed[ticker] = retry_parsed[ticker]
                    local_diagnostics["missing_retry_recovered_tickers"] += len(recovered_now)
                remaining_tickers = [ticker for ticker in remaining_tickers if ticker not in retry_parsed]
                record_pipeline_event(
                    "analyzer",
                    "info",
                    "openai_missing_ticker_retry_completed",
                    module=module.name,
                    retry_attempt=attempt,
                    recovered_tickers=",".join(recovered_now),
                    recovered_count=len(recovered_now),
                    remaining_tickers=",".join(remaining_tickers),
                    remaining_count=len(remaining_tickers),
                )
            missing_tickers = remaining_tickers
        return _BatchRequestResult(
            batch_tickers=batch_tickers,
            parsed=parsed,
            missing_tickers=missing_tickers,
            diagnostics=local_diagnostics,
        )
    except Exception as exc:
        return _BatchRequestResult(
            batch_tickers=batch_tickers,
            error=exc,
            diagnostics=local_diagnostics,
        )


def _request_structured_batch(
    client: Any,
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    model_profile: Any,
    prompt_template: PromptTemplate,
    prompt_context: PromptContext,
    batch_tickers: list[str],
) -> dict[str, dict[str, Any]]:
    batch_payload = module.build_batch_payload(ctx, batch_tickers)
    response = client.responses.create(
        model=model_profile.model,
        max_output_tokens=model_profile.max_output_tokens,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": prompt_template.render_system(prompt_context)}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt_template.render_user(batch_payload, prompt_context)}],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": f"{prompt_template.version}_{prompt_template.name}",
                "schema": prompt_template.output_schema,
                "strict": True,
            }
        },
        prompt_cache_key=_prompt_cache_key(prompt_template, prompt_context),
        **response_temperature_kwargs(model_profile),
    )
    usage_cost = calculate_response_cost(response, model_profile)
    record_pipeline_event(
        "analyzer",
        "info",
        "openai_usage_recorded",
        model=model_profile.model,
        model_profile=model_profile.name,
        module=module.name,
        input_tokens=usage_cost.input_tokens,
        output_tokens=usage_cost.output_tokens,
        cached_input_tokens=usage_cost.cached_input_tokens,
        total_tokens=usage_cost.total_tokens,
        estimated_cost_usd=usage_cost.estimated_cost_usd,
    )
    response_text = getattr(response, "output_text", "").strip()
    prompt_template.validate_response(json.loads(response_text))
    parsed = module.parse_batch_response(response_text, batch_tickers, ctx)
    record_pipeline_event(
        "analyzer",
        "info",
        "openai_response_validated",
        module=module.name,
        ticker_count=len(batch_tickers),
    )
    return parsed


def _split_batches(
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    tickers: list[str],
) -> list[list[str]]:
    token_budget = safe_input_token_budget(resolve_module_model_profile(ctx.model_profile, module.name))
    max_tickers = resolve_module_batch_size(module.name)
    batches: list[list[str]] = []
    current: list[str] = []
    for ticker in tickers:
        candidate = current + [ticker]
        payload = module.build_batch_payload(ctx, candidate)
        over_tokens = estimate_batch_tokens(payload) > token_budget
        over_count = max_tickers is not None and len(candidate) > max_tickers
        should_split = bool(current) and (over_tokens or over_count)
        if should_split:
            batches.append(current)
            current = [ticker]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


def _build_fallback_result(
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    *,
    reason: str,
) -> ModuleResult:
    return ModuleResult(
        results_by_ticker={
            item.ticker: module.fallback_for_ticker(item.ticker, ctx)
            for item in ctx.watchlist
        },
        diagnostics={"fallback_reason": reason},
    )


def _missing_retry_budget(ctx: AnalysisContext) -> int:
    raw_value = ctx.metadata.get("llm_missing_retry_budget", 1)
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return 1


def _resolve_batch_workers(ctx: AnalysisContext, batch_count: int) -> int:
    if batch_count <= 1:
        return 1
    raw_value = ctx.metadata.get("llm_batch_max_workers", os.getenv("LLM_BATCH_MAX_WORKERS", _DEFAULT_LLM_BATCH_MAX_WORKERS))
    try:
        workers = int(raw_value)
    except (TypeError, ValueError):
        workers = _DEFAULT_LLM_BATCH_MAX_WORKERS
    workers = max(1, workers)
    return min(batch_count, workers)


def _validation_retry_budget(ctx: AnalysisContext) -> int:
    raw_value = ctx.metadata.get("llm_validation_retry_budget", 1)
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return 1


def parse_ticker_batch(content: str, expected_tickers: list[str]) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    tickers = parsed.get("tickers")
    if not isinstance(tickers, list):
        raise ValueError("Response missing tickers array")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    expected = set(expected_tickers)
    for entry in tickers:
        if not isinstance(entry, dict):
            raise ValueError("Ticker entry must be an object")
        ticker = str(entry.get("ticker", "")).strip().upper()
        if ticker not in expected:
            raise ValueError(f"Unexpected ticker in response: {ticker}")
        if ticker in seen:
            raise ValueError(f"Duplicate ticker in response: {ticker}")
        seen.add(ticker)
        validated.append(entry)
    return validated


def _should_retry_validation(validated: Any) -> bool:
    counts = validated.counts
    return counts.get("fact_warning", 0) > 0 or counts.get("hallucination_warning", 0) > 0


def _retry_single_ticker_on_validation(
    *,
    client: Any,
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    model_profile: Any,
    prompt_template: PromptTemplate,
    prompt_context: PromptContext,
    ticker: str,
    validator: ResponseValidator,
    retry_budget: int,
    diagnostics: dict[str, Any],
):
    stricter_template = _build_stricter_prompt_template(prompt_template)
    retry_profile = _build_validation_retry_profile(model_profile)
    for attempt in range(1, retry_budget + 1):
        diagnostics["validation_retry_attempts"] += 1
        record_pipeline_event(
            "analyzer",
            "info",
            "openai_validation_retry_started",
            module=module.name,
            ticker=ticker,
            retry_attempt=attempt,
        )
        try:
            parsed = _request_structured_batch(
                client,
                module,
                ctx,
                retry_profile,
                stricter_template,
                replace(
                    prompt_context,
                    metadata={
                        **prompt_context.metadata,
                        "validation_retry": "true",
                        "stricter_prompt": "true",
                    },
                ),
                [ticker],
            )
        except Exception as exc:
            record_pipeline_event(
                "analyzer",
                "warning",
                "openai_validation_retry_failed",
                module=module.name,
                ticker=ticker,
                retry_attempt=attempt,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            continue
        if ticker not in parsed:
            continue
        validated = validator.validate(
            parsed.get(ticker, {}),
            _result_schema_for_ticker(module, ticker, ctx),
            {
                "raw_payload": ctx.raw_payload_by_ticker.get(ticker, {}),
                "fallback": module.fallback_for_ticker(ticker, ctx),
                "intermediate": ctx.intermediate_results.get(ticker, {}),
            },
        )
        if len(validated.warnings) == 0 or not _should_retry_validation(validated):
            diagnostics["validation_retry_recovered_tickers"] += 1
            record_pipeline_event(
                "analyzer",
                "info",
                "openai_validation_retry_completed",
                module=module.name,
                ticker=ticker,
                retry_attempt=attempt,
                recovered=True,
                warning_count=len(validated.warnings),
            )
            return validated
        record_pipeline_event(
            "analyzer",
            "warning",
            "openai_validation_retry_completed",
            module=module.name,
            ticker=ticker,
            retry_attempt=attempt,
            recovered=False,
            warning_count=len(validated.warnings),
            warning_categories=",".join(sorted(validated.counts.keys())),
        )
    return None


def _build_stricter_prompt_template(prompt_template: PromptTemplate) -> PromptTemplate:
    strict_system_suffix = (
        " Validation retry mode: do not paraphrase or invent unsupported values. "
        "Use only values explicitly present in the payload. "
        "If a numeric or event slot is uncertain, write '—' or 'N/A'."
    )
    strict_user_suffix = (
        "\n\n[VALIDATION RETRY RULES]\n"
        "- 이번 재시도에서는 입력 payload에 있는 값만 그대로 사용하세요.\n"
        "- 숫자, 이벤트 날짜, 인물명, 가격 레벨은 추측하거나 보정하지 마세요.\n"
        "- 근거가 없으면 '—' 또는 'N/A'를 쓰세요.\n"
    )
    return replace(
        prompt_template,
        system_template=prompt_template.system_template + strict_system_suffix,
        user_template=prompt_template.user_template + strict_user_suffix,
    )


def _build_validation_retry_profile(model_profile: Any) -> Any:
    model_name = str(getattr(model_profile, "model", "")).strip().lower()
    if model_name.startswith(("o1", "o3", "gpt-5")):
        return model_profile
    return replace(model_profile, temperature=0.1)


def _prompt_cache_key(prompt_template: PromptTemplate, prompt_context: PromptContext) -> str:
    validation_retry = str(prompt_context.metadata.get("validation_retry", "")).strip().lower()
    suffix = ":validation-retry" if validation_retry == "true" else ""
    return f"{prompt_template.version}:{prompt_template.name}{suffix}"


def _result_schema_for_ticker(module: StructuredLLMModule, ticker: str, ctx: AnalysisContext) -> dict[str, str]:
    fallback = ctx.fallback_payload_by_ticker.get(ticker, {})
    schema: dict[str, str] = {}
    for key in module.produces:
        value = fallback.get(key)
        if isinstance(value, str):
            schema[key] = "string"
        elif isinstance(value, list):
            schema[key] = "list"
        elif isinstance(value, dict):
            schema[key] = "dict"
    return schema
