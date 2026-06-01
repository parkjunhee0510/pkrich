"""Search evidence quality metadata for decision outputs."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Mapping

from src.types import TickerDecision

SEARCH_QUALITY_GATE_THRESHOLD = 0.55
OPERATIONAL_EVIDENCE_STATUSES = {
    "cache_error",
    "not_refreshed",
    "provider_error",
    "provider_unavailable",
}
OPERATIONAL_PROVIDER_STATUSES = {
    "budget_blocked",
    "cache_error",
    "not_selected",
    "provider_error",
    "provider_unavailable",
    "rate_limited",
}


def attach_search_quality_shadow(
    decisions: list[TickerDecision],
    search_evidence: Mapping[str, Any] | None,
    *,
    threshold: float = SEARCH_QUALITY_GATE_THRESHOLD,
) -> list[TickerDecision]:
    """Attach search-evidence quality metadata and optionally enforce weak BUY caps."""
    by_ticker = _search_evidence_by_ticker(search_evidence)
    mode = _search_quality_gate_mode()
    enriched: list[TickerDecision] = []
    for decision in decisions:
        ticker = _normalize_ticker(decision.ticker)
        summary = by_ticker.get(ticker)
        score = _search_evidence_score_for_gate(summary)
        gate = _build_search_quality_gate(
            action=decision.action,
            score=score,
            summary=summary,
            threshold=threshold,
            mode=mode,
        )
        confidence_meta = dict(decision.confidence_meta or {})
        confidence_meta["search_evidence_score"] = score
        confidence_meta["search_quality_gate"] = gate
        action = decision.action
        reason = decision.reason
        if gate["mode"] == "enforce" and gate["would_cap_action"]:
            action = str(gate["max_action_if_enforced"])
            gate["enforced"] = True
            gate["original_action"] = decision.action
            gate["capped_action"] = action
            reason = f"{reason} / {_build_search_quality_gate_note(score=score, threshold=threshold)}"
        enriched.append(replace(decision, action=action, reason=reason, confidence_meta=confidence_meta))
    return enriched


def calculate_search_evidence_score(summary: Mapping[str, Any] | None) -> float:
    """Blend normalized search coverage fields into a 0..1 score."""
    if not isinstance(summary, Mapping):
        return 0.0
    if _to_int(summary.get("evidence_count")) <= 0:
        return 0.0

    coverage = _clamp_float(summary.get("coverage_score"))
    freshness = _clamp_float(summary.get("freshness_score"))
    relevance = _clamp_float(summary.get("average_relevance_score"))
    diversity = min(3, max(0, _to_int(summary.get("source_diversity")))) / 3.0
    score = (0.40 * coverage) + (0.25 * freshness) + (0.20 * relevance) + (0.15 * diversity)
    return round(score, 4)


def _search_evidence_score_for_gate(summary: Mapping[str, Any] | None) -> float | None:
    if summary is None or _operational_gap_reason(summary):
        return None
    return calculate_search_evidence_score(summary)


def _build_search_quality_gate(
    *,
    action: str,
    score: float | None,
    summary: Mapping[str, Any] | None,
    threshold: float,
    mode: str,
) -> dict[str, Any]:
    evidence_count = _to_int(summary.get("evidence_count")) if isinstance(summary, Mapping) else 0
    source_diversity = _to_int(summary.get("source_diversity")) if isinstance(summary, Mapping) else 0
    evidence_status = _summary_text(summary, "evidence_status")
    provider_status = _summary_text(summary, "provider_status")
    priority_for_refresh = bool(summary.get("priority_for_refresh")) if isinstance(summary, Mapping) else False
    would_cap = score is not None and score < threshold and str(action).lower() == "buy"
    operational_reason = _operational_gap_reason(summary)

    if operational_reason:
        reason = operational_reason
    elif score is None:
        reason = "search_evidence_unavailable"
    elif evidence_count <= 0:
        reason = "no_recent_search_evidence"
    elif would_cap:
        reason = "low_recent_search_evidence"
    else:
        reason = "search_evidence_sufficient"

    return {
        "mode": mode,
        "threshold": round(_clamp_float(threshold), 4),
        "max_action_if_enforced": "watch",
        "would_cap_action": would_cap,
        "enforced": False,
        "reason": reason,
        "evidence_count": evidence_count,
        "source_diversity": source_diversity,
        "evidence_status": evidence_status,
        "provider_status": provider_status,
        "priority_for_refresh": priority_for_refresh,
    }


def _search_quality_gate_mode() -> str:
    raw_mode = os.getenv("DECISION_SEARCH_QUALITY_GATE_MODE", "shadow").strip().lower()
    if raw_mode in {"1", "true", "on", "yes", "enforce", "enforced"}:
        return "enforce"
    return "shadow"


def _build_search_quality_gate_note(*, score: float | None, threshold: float) -> str:
    score_text = "N/A" if score is None else f"{score:.2f}"
    return (
        f"검색 근거 품질 게이트 적용: search_evidence_score "
        f"{score_text} < {threshold:.2f}라서 buy를 watch로 제한"
    )


def _search_evidence_by_ticker(search_evidence: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(search_evidence, Mapping):
        return {}
    raw = search_evidence.get("by_ticker", {})
    if not isinstance(raw, Mapping):
        return {}
    return {
        _normalize_ticker(ticker): summary
        for ticker, summary in raw.items()
        if _normalize_ticker(ticker) and isinstance(summary, Mapping)
    }


def _normalize_ticker(ticker: object) -> str:
    return str(ticker or "").strip().upper()


def _summary_text(summary: Mapping[str, Any] | None, key: str) -> str:
    if not isinstance(summary, Mapping):
        return "unavailable"
    return str(summary.get(key) or "").strip().lower()


def _operational_gap_reason(summary: Mapping[str, Any] | None) -> str:
    if not isinstance(summary, Mapping):
        return ""
    evidence_status = _summary_text(summary, "evidence_status")
    if evidence_status in OPERATIONAL_EVIDENCE_STATUSES:
        return evidence_status
    provider_status = _summary_text(summary, "provider_status")
    if provider_status in OPERATIONAL_PROVIDER_STATUSES:
        return provider_status
    return ""


def _clamp_float(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _to_int(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0
