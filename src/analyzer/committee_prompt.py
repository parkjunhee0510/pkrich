from __future__ import annotations

import json
from typing import Any

from src.types import TickerAnalysis


def build_growth_analyst_prompt(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    role_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _build_role_prompt(
        "growth_analyst",
        analysis,
        round_name=round_name,
        profile_name=profile_name,
        max_summary_sentences=max_summary_sentences,
        focus="growth, catalyst durability, and upside setup",
        role_outputs=role_outputs,
    )


def build_value_skeptic_prompt(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    role_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _build_role_prompt(
        "value_skeptic",
        analysis,
        round_name=round_name,
        profile_name=profile_name,
        max_summary_sentences=max_summary_sentences,
        focus="valuation risk, downside asymmetry, and quality of earnings",
        role_outputs=role_outputs,
    )


def build_risk_manager_prompt(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    role_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _build_role_prompt(
        "risk_manager",
        analysis,
        round_name=round_name,
        profile_name=profile_name,
        max_summary_sentences=max_summary_sentences,
        focus="thesis breaks, invalidation levels, and explicit objections",
        role_outputs=role_outputs,
    )


def build_macro_strategist_prompt(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    role_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _build_role_prompt(
        "macro_strategist",
        analysis,
        round_name=round_name,
        profile_name=profile_name,
        max_summary_sentences=max_summary_sentences,
        focus="macro regime, rate sensitivity, and cross-asset pressure",
        role_outputs=role_outputs,
    )


def build_pm_prompt(
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    role_outputs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _build_role_prompt(
        "pm",
        analysis,
        round_name=round_name,
        profile_name=profile_name,
        max_summary_sentences=max_summary_sentences,
        focus="final synthesis, confidence, and escalation judgment",
        role_outputs=role_outputs,
    )


def _build_role_prompt(
    role: str,
    analysis: TickerAnalysis | dict[str, Any],
    *,
    round_name: str,
    profile_name: str,
    max_summary_sentences: int,
    focus: str,
    role_outputs: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    ticker_context = _analysis_payload(analysis)
    structured_role_outputs = _normalize_role_outputs(role_outputs or {})
    contract = _committee_contract()
    system = (
        f"You are the {role} on the committee. "
        f"Round: {round_name}. Profile: {profile_name}. "
        f"Limit summaries to {max_summary_sentences} sentence(s). "
        f"Focus on {focus}. "
        f"Allowed stances: {', '.join(contract['allowed_stances'])}. "
        f"Required fields for {role}: {', '.join(contract['required_fields'][role])}. "
        "Return concise, structured JSON-compatible output. "
        "JSON key는 영어로 유지하고, summary 값은 반드시 한국어로 작성하세요. "
        "Do not write English prose in summary values."
    )
    user = (
        f"Ticker context: {json.dumps(ticker_context, ensure_ascii=True, sort_keys=True)}\n"
        f"Prior role outputs: {json.dumps(structured_role_outputs, ensure_ascii=True, sort_keys=True)}\n"
        f"Committee focus: {focus}\n"
        "summary는 한국어로 작성하고, ticker/metric/source 같은 고유명사와 숫자만 원문 표기를 허용합니다."
    )
    return {
        "role": role,
        "round": round_name,
        "profile": profile_name,
        "context": {
            "ticker": ticker_context,
            "role_outputs": structured_role_outputs,
        },
        "contract": contract,
        "system": system,
        "user": user,
    }


def _analysis_payload(analysis: TickerAnalysis | dict[str, Any]) -> dict[str, Any]:
    if isinstance(analysis, dict):
        payload = dict(analysis)
        payload.pop("committee_analysis", None)
        return payload
    return {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "date": analysis.date,
        "summary": analysis.summary,
        "key_news": analysis.key_news,
        "financial_highlights": analysis.financial_highlights,
        "risks_or_watchpoints": analysis.risks_or_watchpoints,
        "signal_or_takeaway": analysis.signal_or_takeaway,
        "data_snapshot": analysis.data_snapshot,
        "fundamentals": analysis.fundamentals,
        "price_action": analysis.price_action,
        "quarterly_financials": analysis.quarterly_financials,
        "upcoming_events": analysis.upcoming_events,
        "news_tone": analysis.news_tone,
        "trade_frame": analysis.trade_frame,
        "options_summary": analysis.options_summary,
        "signal_history": analysis.signal_history,
        "sector_comparison": analysis.sector_comparison,
        "peer_rank": analysis.peer_rank,
        "valuation_score": analysis.valuation_score,
        "analysis_consensus": analysis.analysis_consensus,
        "historical_prices": analysis.historical_prices,
    }


def _normalize_role_outputs(role_outputs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for role, payload in role_outputs.items():
        normalized[role] = {
            "role": str(payload.get("role", role)),
            "profile": str(payload.get("profile", "")),
            "round": str(payload.get("round", "")),
            "stance": str(payload.get("stance", "watch")),
            "action": str(payload.get("action", "watch")),
            "confidence": payload.get("confidence", 0),
            "strong_objection": bool(payload.get("strong_objection", False)),
            "summary": str(payload.get("summary", "")),
        }
    return normalized


def _committee_contract() -> dict[str, Any]:
    allowed_stances = ["strong_buy", "buy", "watch", "reduce", "avoid"]
    required_fields = {
        "growth_analyst": ["stance", "summary"],
        "value_skeptic": ["stance", "summary"],
        "risk_manager": ["stance", "summary", "strong_objection"],
        "macro_strategist": ["stance", "summary", "strong_objection"],
        "pm": ["stance", "summary", "confidence"],
    }
    return {
        "allowed_stances": allowed_stances,
        "required_fields": required_fields,
    }
