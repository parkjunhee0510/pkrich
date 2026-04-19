from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult
from src.analyzer.prompts import PromptContext, get_prompt_template
from src.utils.env import load_dotenv
from src.utils.model_config import load_model_profile
from src.utils.pipeline_logging import record_pipeline_event


class WeeklyInsightModule(AnalysisModule):
    name = "weekly_insight_module"
    produces = {"weekly_report"}
    llm_required = True
    priority = 100

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        weekly_inputs = dict(ctx.metadata.get("weekly_inputs", {}))
        fallback_report = build_fallback_weekly_report(weekly_inputs)

        load_dotenv()
        if not os.getenv("OPENAI_API_KEY"):
            return ModuleResult(
                portfolio_result={"weekly_report": fallback_report},
                diagnostics={"fallback_used": True, "reason": "missing_api_key"},
            )

        model_profile = ctx.model_profile or load_model_profile()
        prompt_template = get_prompt_template(model_profile.prompt_version, self.name)
        prompt_ctx = PromptContext(
            run_date=ctx.run_date,
            macro_context=ctx.macro_context,
            model_profile=model_profile,
        )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.responses.create(
                model=model_profile.model,
                max_output_tokens=min(model_profile.max_output_tokens, 1800),
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": prompt_template.render_system(prompt_ctx)}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt_template.render_user(weekly_inputs, prompt_ctx)}],
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
            )
            content = getattr(response, "output_text", "").strip()
            payload = json.loads(content)
            report = _normalize_weekly_report(payload, fallback_report)
            prompt_template.validate_response(report)
            return ModuleResult(
                portfolio_result={"weekly_report": report},
                diagnostics={"fallback_used": False, "model": model_profile.model},
            )
        except Exception as exc:
            record_pipeline_event(
                "analyzer",
                "warning",
                "weekly_report_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            return ModuleResult(
                portfolio_result={"weekly_report": fallback_report},
                diagnostics={"fallback_used": True, "reason": type(exc).__name__},
            )


def build_fallback_weekly_report(payload: dict[str, Any]) -> dict[str, object]:
    market_moves = payload.get("market_moves", []) or []
    sector_performance = payload.get("sector_performance", []) or []
    top_movers = payload.get("top_movers", []) or []
    signal_summary = payload.get("signal_summary", []) or []
    risk_recommendations = payload.get("portfolio_risk", {}).get("recommendations", []) or []
    action_plan_items = payload.get("top_conviction_items", []) or []
    macro_events = payload.get("next_macro_events", []) or []
    risk_grade = str(payload.get("portfolio_risk", {}).get("risk_grade", "")).strip()
    regime_label = _regime_label(payload.get("market_regime"))

    market_summary_parts: list[str] = []
    if regime_label:
        market_summary_parts.append(f"{regime_label} 환경")
    if market_moves:
        market_summary_parts.append(
            ", ".join(f"{item.get('label', '시장')} {item.get('weekly_change', 'N/A')}" for item in market_moves[:3])
        )
    if sector_performance:
        top_sector = sector_performance[0]
        market_summary_parts.append(
            f"주도 섹터는 {top_sector.get('sector', 'N/A')} ({top_sector.get('average_weekly_change', 'N/A')})"
        )
    market_environment_summary = ". ".join(part for part in market_summary_parts if part) or "시장 환경 데이터가 충분하지 않습니다."

    mover_items: list[dict[str, str]] = []
    for item in top_movers[:3]:
        mover_items.append(
            {
                "ticker": str(item.get("ticker", "N/A")),
                "name": str(item.get("name", item.get("ticker", "N/A"))),
                "weekly_change": str(item.get("weekly_change", "N/A")),
                "catalyst": str(item.get("catalyst", "반복 촉매 데이터 부족")),
                "decision_change": str(item.get("decision_change", "이번 주 decision 변화 데이터 없음")),
            }
        )
    mover_summary = (
        f"주간 절대 변동 기준 상위 종목은 {', '.join(item['ticker'] for item in mover_items)}입니다."
        if mover_items
        else "이번 주 핵심 이동 종목 데이터가 충분하지 않습니다."
    )

    signal_review_summary = signal_summary[0] if signal_summary else "이번 주 검증 가능한 시그널 성과가 제한적입니다."
    risk_items: list[str] = []
    if risk_grade:
        risk_items.append(f"현재 포트폴리오 리스크 등급은 {risk_grade}입니다.")
    for event in macro_events[:3]:
        risk_items.append(
            f"{event.get('date', 'N/A')} {event.get('label', '매크로 이벤트')} (D-{event.get('days_until', '?')})"
        )
    if not risk_items:
        risk_items.append("다음 주 주목할 리스크 이벤트 데이터가 충분하지 않습니다.")

    action_items: list[str] = []
    for item in action_plan_items[:3]:
        action_items.append(
            f"{item.get('ticker', 'N/A')} {item.get('action', 'watch')} / conviction {item.get('conviction', 'N/A')} / {item.get('catalyst', '촉매 없음')}"
        )
    if not action_items:
        action_items = list(payload.get("action_items", [])[:3]) or ["다음 주 액션 플랜 데이터가 충분하지 않습니다."]

    portfolio_suggestions = [str(item) for item in risk_recommendations[:4]] or ["포트폴리오 조정 제안 데이터가 충분하지 않습니다."]

    summary = " ".join(
        [
            market_environment_summary,
            mover_summary,
            signal_review_summary,
        ]
    ).strip()

    return {
        "headline": f"{payload.get('iso_year', 'N/A')}-W{payload.get('iso_week', 'N/A')} 주간 리포트",
        "summary": summary or "주간 리포트 데이터를 요약할 수 없습니다.",
        "market_environment": {
            "summary": market_environment_summary,
            "details": _coerce_lines(payload.get("market_environment_details"))
            or ["시장 환경 관련 세부 데이터가 충분하지 않습니다."],
        },
        "top_movers": {
            "summary": mover_summary,
            "items": mover_items,
        },
        "signal_review": {
            "summary": signal_review_summary,
            "details": [str(line) for line in signal_summary[:4]] or ["시그널 성과 데이터가 충분하지 않습니다."],
        },
        "risk_points": {
            "summary": risk_items[0] if risk_items else "리스크 포인트 데이터가 충분하지 않습니다.",
            "items": risk_items,
        },
        "next_week_action_plan": {
            "summary": action_items[0] if action_items else "다음 주 액션 플랜 데이터가 충분하지 않습니다.",
            "items": action_items,
        },
        "portfolio_suggestions": {
            "summary": portfolio_suggestions[0] if portfolio_suggestions else "포트폴리오 제안 데이터가 충분하지 않습니다.",
            "items": portfolio_suggestions,
        },
    }


def _normalize_weekly_report(payload: dict[str, Any], fallback: dict[str, object]) -> dict[str, object]:
    result = dict(fallback)
    for key in ("headline", "summary"):
        value = str(payload.get(key, "")).strip()
        min_length = 10 if key == "headline" else 20
        if value and len(value) >= min_length:
            result[key] = value

    section_defaults = {
        "market_environment": {"summary": "", "details": []},
        "top_movers": {"summary": "", "items": []},
        "signal_review": {"summary": "", "details": []},
        "risk_points": {"summary": "", "items": []},
        "next_week_action_plan": {"summary": "", "items": []},
        "portfolio_suggestions": {"summary": "", "items": []},
    }
    for section, default_value in section_defaults.items():
        raw = payload.get(section, {})
        if not isinstance(raw, dict):
            continue
        merged = dict(default_value)
        merged.update(raw)
        if "summary" in merged:
            raw_summary = str(merged.get("summary", "")).strip()
            fallback_summary = str((fallback.get(section, {}) or {}).get("summary", "")).strip() if isinstance(fallback.get(section), dict) else ""
            merged["summary"] = raw_summary if len(raw_summary) >= 10 else fallback_summary
        if "details" in merged:
            details = _coerce_lines(merged.get("details"))
            fallback_details = (
                _coerce_lines((fallback.get(section, {}) or {}).get("details"))
                if isinstance(fallback.get(section), dict)
                else []
            )
            merged["details"] = details or fallback_details
        if "items" in merged:
            if section == "top_movers":
                merged["items"] = [
                    {
                        "ticker": str(item.get("ticker", "N/A")),
                        "name": str(item.get("name", item.get("ticker", "N/A"))),
                        "weekly_change": str(item.get("weekly_change", "N/A")),
                        "catalyst": str(item.get("catalyst", "N/A")),
                        "decision_change": str(item.get("decision_change", "N/A")),
                    }
                    for item in merged.get("items", [])
                    if isinstance(item, dict)
                ]
                if not merged["items"] and isinstance(fallback.get(section), dict):
                    merged["items"] = list((fallback.get(section, {}) or {}).get("items", []))
            else:
                items = _coerce_lines(merged.get("items"))
                fallback_items = (
                    _coerce_lines((fallback.get(section, {}) or {}).get("items"))
                    if isinstance(fallback.get(section), dict)
                    else []
                )
                merged["items"] = items or fallback_items
        result[section] = merged
    return result


def _coerce_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _regime_label(regime: Any) -> str:
    if isinstance(regime, dict):
        name = str(regime.get("regime", "")).strip()
    else:
        name = str(getattr(regime, "regime", "")).strip()
    return {
        "risk_on": "위험선호",
        "neutral": "중립",
        "risk_off": "위험회피",
    }.get(name, name)

