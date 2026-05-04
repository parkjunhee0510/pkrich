from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.decision.base import FactorScore
from src.decision.data_quality import DataQualityResult, calculate_data_quality_result
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


@dataclass(frozen=True)
class ConfidenceMeta:
    data_quality: float
    evidence_coverage: float
    evidence_consistency: float
    model_agreement: float
    confidence_gate: float
    data_quality_result: DataQualityResult

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "data_quality": self.data_quality,
            "evidence_coverage": self.evidence_coverage,
            "evidence_consistency": self.evidence_consistency,
            "model_agreement": self.model_agreement,
            "confidence_gate": self.confidence_gate,
        }
        payload.update(self.data_quality_result.to_meta())
        return payload


def calculate_data_quality(
    analysis: TickerAnalysis,
    quality_summary: dict[str, Any] | None = None,
    *,
    data: CollectedTickerData | None = None,
    run_date: date | None = None,
    macro_context: dict[str, Any] | None = None,
) -> float:
    return calculate_data_quality_result(
        analysis=analysis,
        data=data,
        run_date=run_date,
        quality_summary=quality_summary,
        macro_context=macro_context,
    ).score


def calculate_evidence_coverage(
    analysis: TickerAnalysis,
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
) -> float:
    macro_context = macro_context or {}
    portfolio_risk = portfolio_risk or {}
    checks = [
        bool(analysis.price_action),
        bool(analysis.key_news or analysis.news_tone),
        bool(analysis.quarterly_financials or analysis.fundamentals),
        bool(analysis.peer_rank or analysis.sector_comparison),
        bool(analysis.upcoming_events or macro_context.get("macro_events")),
        bool(portfolio_risk or analysis.signal_history),
    ]
    return round(sum(1 for present in checks if present) / len(checks), 4)


def calculate_evidence_consistency(
    analysis: TickerAnalysis,
    regime: MarketRegime,
    factor_scores_by_name: dict[str, FactorScore],
    macro_context: dict[str, Any] | None = None,
) -> float:
    macro_context = macro_context or {}
    pair_scores: list[float] = []

    momentum_direction = _sign(factor_scores_by_name.get("momentum", FactorScore(0, 0.0, "")).value)
    news_direction = _tone_direction(analysis.news_tone)
    takeaway_direction = _text_direction(analysis.signal_or_takeaway)
    peer_direction = _peer_direction(analysis.peer_rank)
    earnings_direction = _earnings_direction(analysis.quarterly_financials)
    macro_direction = _macro_direction(macro_context)
    regime_direction = -1 if regime.regime in {"risk_off", "defensive_bias"} else 1

    pair_scores.append(_pair_alignment(momentum_direction, news_direction))
    pair_scores.append(_pair_alignment(momentum_direction, takeaway_direction))
    pair_scores.append(_pair_alignment(peer_direction, takeaway_direction))
    pair_scores.append(_pair_alignment(earnings_direction, takeaway_direction))
    if macro_direction != 0:
        pair_scores.append(_pair_alignment(macro_direction, regime_direction))

    usable_scores = [score for score in pair_scores if score >= 0]
    if not usable_scores:
        return 0.6
    return _clamp(sum(usable_scores) / len(usable_scores))


def calculate_model_agreement(
    analysis_consensus: dict[str, Any] | None = None,
) -> float:
    consensus = analysis_consensus or {}
    status = str(consensus.get("status", "")).strip().lower()
    direction_agreement = bool(consensus.get("direction_agreement", False))
    had_tie_break = bool(consensus.get("had_tie_break", False))

    if not consensus or status in {"", "single", "not_applicable"}:
        return 0.6
    if status == "conflicted":
        return 0.4
    if direction_agreement and not had_tie_break:
        return 0.9
    if status in {"resolved", "tie_break"} or had_tie_break:
        return 0.65
    if direction_agreement:
        return 0.8
    return 0.55


def calculate_confidence_gate(meta: ConfidenceMeta) -> float:
    gate = (
        0.40 * meta.data_quality
        + 0.25 * meta.evidence_coverage
        + 0.20 * meta.evidence_consistency
        + 0.15 * meta.model_agreement
    )
    return _clamp(round(gate, 4))


def calculate_final_conviction(raw_conviction: int, meta: ConfidenceMeta) -> int:
    final_conviction = round(raw_conviction * (0.60 + 0.40 * meta.confidence_gate))
    return max(0, min(100, final_conviction))


def evaluate_confidence_meta(
    *,
    analysis: TickerAnalysis,
    data: CollectedTickerData | None = None,
    run_date: date | None = None,
    regime: MarketRegime,
    factor_scores_by_name: dict[str, FactorScore],
    macro_context: dict[str, Any] | None,
    portfolio_risk: dict[str, Any] | None,
    analysis_consensus: dict[str, Any] | None,
    quality_summary: dict[str, Any] | None,
) -> ConfidenceMeta:
    data_quality_result = calculate_data_quality_result(
        analysis=analysis,
        data=data,
        run_date=run_date,
        quality_summary=quality_summary,
        macro_context=macro_context,
    )
    data_quality = data_quality_result.score
    evidence_coverage = calculate_evidence_coverage(analysis, macro_context, portfolio_risk)
    evidence_consistency = calculate_evidence_consistency(
        analysis,
        regime,
        factor_scores_by_name,
        macro_context,
    )
    model_agreement = calculate_model_agreement(analysis_consensus)
    partial_meta = ConfidenceMeta(
        data_quality=data_quality,
        evidence_coverage=evidence_coverage,
        evidence_consistency=evidence_consistency,
        model_agreement=model_agreement,
        confidence_gate=0.0,
        data_quality_result=data_quality_result,
    )
    return ConfidenceMeta(
        data_quality=data_quality,
        evidence_coverage=evidence_coverage,
        evidence_consistency=evidence_consistency,
        model_agreement=model_agreement,
        confidence_gate=calculate_confidence_gate(partial_meta),
        data_quality_result=data_quality_result,
    )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, round(float(value), 4)))


def _sign(value: int | float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _pair_alignment(left: int, right: int) -> float:
    if left == 0 or right == 0:
        return 0.6
    if left == right:
        return 0.9
    return 0.3


def _tone_direction(news_tone: dict[str, Any]) -> int:
    label = str(news_tone.get("label", "")).strip().lower()
    if label in {"bullish", "positive"}:
        return 1
    if label in {"bearish", "negative"}:
        return -1
    score = news_tone.get("score", 0)
    try:
        return _sign(float(score))
    except (TypeError, ValueError):
        return 0


def _text_direction(text: str) -> int:
    lowered = text.lower()
    positive_tokens = ("improv", "strong", "bull", "positive", "constructive", "upside", "beat", "long")
    negative_tokens = ("weak", "bear", "negative", "risk", "downside", "fade", "miss", "short")
    positive_hits = sum(token in lowered for token in positive_tokens)
    negative_hits = sum(token in lowered for token in negative_tokens)
    if positive_hits > negative_hits:
        return 1
    if negative_hits > positive_hits:
        return -1
    return 0


def _peer_direction(peer_rank: dict[str, Any]) -> int:
    try:
        per_pctl = float(peer_rank.get("per_pctl", 50))
        rs_pctl = float(peer_rank.get("rs_pctl", 50))
    except (TypeError, ValueError):
        return 0
    if rs_pctl >= 65 and per_pctl <= 40:
        return 1
    if rs_pctl <= 35 and per_pctl >= 60:
        return -1
    return 0


def _earnings_direction(quarterly_financials: list[dict[str, Any]]) -> int:
    if not quarterly_financials:
        return 0
    score = 0
    for quarter in quarterly_financials[:4]:
        beat_miss = str(quarter.get("beat_miss", "")).strip().lower()
        if beat_miss == "beat":
            score += 1
        elif beat_miss == "miss":
            score -= 1
    return _sign(score)


def _macro_direction(macro_context: dict[str, Any]) -> int:
    events = macro_context.get("macro_events", [])
    if not isinstance(events, list) or not events:
        return 0
    score = 0
    for event in events[:3]:
        text = " ".join(
            str(event.get(key, ""))
            for key in ("direction", "severity", "summary", "summary_ko", "event_type")
        ).lower()
        if any(token in text for token in ("positive", "bull", "easing", "supportive", "low")):
            score += 1
        if any(token in text for token in ("negative", "bear", "tight", "disruption", "high")):
            score -= 1
    return _sign(score)
