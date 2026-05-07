"""Search evidence quality metadata for decision outputs."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from src.types import TickerDecision

SEARCH_QUALITY_GATE_THRESHOLD = 0.55


def attach_search_quality_shadow(
    decisions: list[TickerDecision],
    search_evidence: Mapping[str, Any] | None,
    *,
    threshold: float = SEARCH_QUALITY_GATE_THRESHOLD,
) -> list[TickerDecision]:
    """Attach search-evidence quality metadata without changing actions."""
    by_ticker = _search_evidence_by_ticker(search_evidence)
    enriched: list[TickerDecision] = []
    for decision in decisions:
        ticker = _normalize_ticker(decision.ticker)
        summary = by_ticker.get(ticker)
        score = calculate_search_evidence_score(summary) if summary is not None else None
        gate = _build_search_quality_gate(
            action=decision.action,
            score=score,
            summary=summary,
            threshold=threshold,
        )
        confidence_meta = dict(decision.confidence_meta or {})
        confidence_meta["search_evidence_score"] = score
        confidence_meta["search_quality_gate"] = gate
        enriched.append(replace(decision, confidence_meta=confidence_meta))
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


def _build_search_quality_gate(
    *,
    action: str,
    score: float | None,
    summary: Mapping[str, Any] | None,
    threshold: float,
) -> dict[str, Any]:
    evidence_count = _to_int(summary.get("evidence_count")) if isinstance(summary, Mapping) else 0
    source_diversity = _to_int(summary.get("source_diversity")) if isinstance(summary, Mapping) else 0
    would_cap = score is not None and score < threshold and str(action).lower() == "buy"

    if score is None:
        reason = "search_evidence_unavailable"
    elif evidence_count <= 0:
        reason = "no_recent_search_evidence"
    elif would_cap:
        reason = "low_recent_search_evidence"
    else:
        reason = "search_evidence_sufficient"

    return {
        "mode": "shadow",
        "threshold": round(_clamp_float(threshold), 4),
        "max_action_if_enforced": "watch",
        "would_cap_action": would_cap,
        "reason": reason,
        "evidence_count": evidence_count,
        "source_diversity": source_diversity,
    }


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
