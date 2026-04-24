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
    full_payload = _analysis_payload(analysis)
    ticker_context = _slim_payload_for_role(full_payload, role)
    structured_role_outputs = _normalize_role_outputs(role_outputs or {})
    contract = _committee_contract()
    persona = _ROLE_PERSONAS[role]
    stance_policy = _ROLE_STANCE_POLICY[role]
    system = (
        f"You are the {role} on an investment committee. {persona} "
        f"Round: {round_name}. Profile: {profile_name}. "
        f"Limit summaries to {max_summary_sentences} sentence(s). "
        f"Focus on {focus}. "
        f"Allowed stances for this role: {', '.join(stance_policy['allowed'])}. "
        f"Required fields for {role}: {', '.join(contract['required_fields'][role])}. "
        "Base every claim on concrete numbers/levels/events from the provided ticker context. "
        "Do NOT parrot other roles — add a viewpoint only this role would surface. "
        "Return concise, structured JSON-compatible output. "
        "JSON key는 영어로 유지하고, summary 값은 반드시 한국어로 작성하세요. "
        "Do not write English prose in summary values."
    )
    user = (
        f"Ticker context (role-slimmed): {json.dumps(ticker_context, ensure_ascii=True, sort_keys=True)}\n"
        f"Prior role outputs: {json.dumps(structured_role_outputs, ensure_ascii=True, sort_keys=True)}\n"
        f"Committee focus: {focus}\n"
        f"Persona guidance: {persona}\n"
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


_ROLE_PERSONAS: dict[str, str] = {
    "growth_analyst": (
        "성장주 매니저. 실적 가속, 매출/EPS 추세, AI/신제품 등 상방 촉매 중심으로 판단하며, "
        "카탈리스트가 명확할 때 strong_buy/buy에 적극적. 단순 모멘텀 추격은 경계."
    ),
    "value_skeptic": (
        "가치 회의론자. PER·P/B·목표가 괴리·현금흐름 품질을 의심하며, 과열·밸류에이션 갭을 최소 2개 이상 "
        "구체적 숫자로 반박. 낙관론에 동조하지 말 것 — watch/reduce/avoid로 기울어야 할 때는 주저 없이."
    ),
    "risk_manager": (
        "리스크 매니저. SMA50/SMA200·52주 고점/저점·RSI·invalidation level을 기준으로 하방 시나리오 먼저 제시. "
        "strong_objection=true는 명확한 손절/추세 훼손 조건을 한 줄로 특정할 수 있을 때만."
    ),
    "macro_strategist": (
        "매크로 전략가. 금리/달러/유가/섹터 로테이션·리스크온-오프 레짐 관점에서 해당 티커의 민감도를 평가. "
        "개별 기업 지표보다 거시·섹터 상대강도·상관관계를 우선. 티커 고유 이슈 반복 금지."
    ),
    "pm": (
        "포트폴리오 매니저. 네 역할 의견을 종합해 최종 stance·confidence를 결정. "
        "의견이 갈리면 confidence를 보수적으로. 합의가 있어도 반대 근거 한 줄 포함."
    ),
}

_ROLE_STANCE_POLICY: dict[str, dict[str, Any]] = {
    "growth_analyst": {"allowed": ["strong_buy", "buy", "watch", "reduce"]},
    "value_skeptic": {"allowed": ["buy", "watch", "reduce", "avoid"]},
    "risk_manager": {"allowed": ["buy", "watch", "reduce", "avoid"]},
    "macro_strategist": {"allowed": ["strong_buy", "buy", "watch", "reduce", "avoid"]},
    "pm": {"allowed": ["strong_buy", "buy", "watch", "reduce", "avoid"]},
}

_ROLE_FIELD_WHITELIST: dict[str, tuple[str, ...]] = {
    "growth_analyst": (
        "ticker", "name", "date", "summary", "signal_or_takeaway",
        "key_news", "financial_highlights", "fundamentals",
        "quarterly_financials", "upcoming_events", "news_tone",
        "sector_comparison", "peer_rank", "analysis_consensus",
    ),
    "value_skeptic": (
        "ticker", "name", "date", "summary",
        "fundamentals", "valuation_score", "peer_rank",
        "analysis_consensus", "quarterly_financials", "financial_highlights",
        "risks_or_watchpoints",
    ),
    "risk_manager": (
        "ticker", "name", "date", "summary",
        "price_action", "data_snapshot", "trade_frame",
        "options_summary", "risks_or_watchpoints", "upcoming_events",
        "signal_history",
    ),
    "macro_strategist": (
        "ticker", "name", "date", "summary",
        "sector_comparison", "news_tone", "upcoming_events",
        "data_snapshot", "price_action",
    ),
    "pm": (
        "ticker", "name", "date", "summary", "signal_or_takeaway",
        "key_news", "financial_highlights", "risks_or_watchpoints",
        "fundamentals", "price_action", "sector_comparison",
        "valuation_score", "analysis_consensus", "upcoming_events",
        "trade_frame",
    ),
}

_ALWAYS_DROP_FIELDS = ("historical_prices",)


def _slim_payload_for_role(payload: dict[str, Any], role: str) -> dict[str, Any]:
    whitelist = _ROLE_FIELD_WHITELIST.get(role)
    if whitelist is None:
        slim = {k: v for k, v in payload.items() if k not in _ALWAYS_DROP_FIELDS}
    else:
        slim = {k: payload[k] for k in whitelist if k in payload}
    if "signal_history" in slim:
        slim["signal_history"] = _truncate_signal_history(slim["signal_history"])
    if "price_action" in slim and isinstance(slim["price_action"], dict):
        slim["price_action"] = _compact_price_action(slim["price_action"])
    return slim


def _truncate_signal_history(value: Any, *, limit: int = 10) -> Any:
    if isinstance(value, list):
        return value[-limit:]
    return value


def _compact_price_action(pa: dict[str, Any]) -> dict[str, Any]:
    compact = dict(pa)
    for key in ("ohlc", "intraday", "tick_data", "raw_prices"):
        compact.pop(key, None)
    return compact
