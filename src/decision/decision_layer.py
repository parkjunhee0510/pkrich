"""Per-ticker decision layer with plugin-based factor scoring."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.decision.base import FactorScore
from src.decision.config import normalize_decision_config
from src.decision.registry import build_factor_registry
from src.decision.scorer import ConvictionScorer
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path("config/decision_weights.yaml")
_DEFAULT_FACTORS = {
    "valuation": {"min": 0, "max": 20},
    "momentum": {"min": 0, "max": 20},
    "catalyst_recency": {"min": -10, "max": 20},
    "signal_track_record": {"min": -10, "max": 15},
    "news_tone": {"min": -5, "max": 10},
    "regime_adjustment": {"min": -15, "max": 15},
    "earnings_pattern": {"min": -10, "max": 10},
    "fundamentals": {"min": 0, "max": 10},
    "macro_event": {"min": -8, "max": 6},
    "macro_regime": {"min": -6, "max": 8},
    "peer_rank": {"min": -4, "max": 8},
    "portfolio_risk": {"min": -10, "max": 0},
}
_DEFAULT_THRESHOLDS = {"buy": 65, "buy_risk_off": 75, "avoid": 35}
_DEFAULT_VALID_UNTIL = {"earnings_window_days": 30, "default_days": 7}
_DEFAULT_REGIME_MULTIPLIERS = {
    "risk_on": {},
    "risk_off": {},
    "neutral": {},
    "reflation": {},
    "defensive_bias": {},
}


def generate_decisions(
    analyses: list[TickerAnalysis],
    collected: dict[str, CollectedTickerData] | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any] | None,
    run_date: date,
    *,
    portfolio_risk: dict[str, Any] | None = None,
    macro_context: dict[str, Any] | None = None,
) -> list[TickerDecision]:
    try:
        config = _load_weights()
        collected = collected or {}
        signal_stats = signal_stats or {}
        decision_context = {
            **signal_stats,
            "_portfolio_risk": portfolio_risk or {},
            "_macro_context": macro_context or {},
        }
        return [
            _decide_ticker(analysis, collected.get(analysis.ticker), regime, decision_context, run_date, config)
            for analysis in analyses
        ]
    except Exception:
        logger.exception("Decision layer failed")
        return []


def _decide_ticker(
    analysis: TickerAnalysis,
    data: CollectedTickerData | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any],
    run_date: date,
    config: dict[str, Any],
) -> TickerDecision:
    registry = config["_registry"]
    scorer = config["_scorer"]
    factor_scores_by_name: dict[str, FactorScore] = {}
    factors: dict[str, float] = {}

    for factor in registry.all():
        score = factor.score(analysis, data, regime, signal_stats)
        low, high = factor.weight_range
        clamped_value = max(low, min(high, int(score.value)))
        final_score = FactorScore(
            value=clamped_value,
            confidence=score.confidence,
            reasoning=score.reasoning,
        )
        factor_scores_by_name[factor.name] = final_score
        factors[factor.name] = float(final_score.value)

    weighted_values = scorer.weighted_values(factor_scores_by_name, regime.regime)
    conviction = scorer.calculate(factor_scores_by_name, regime.regime)

    thresholds = config.get("thresholds", {})
    buy_threshold = thresholds.get("buy_risk_off", 75) if regime.regime == "risk_off" else thresholds.get("buy", 65)
    avoid_threshold = thresholds.get("avoid", 35)

    if conviction >= buy_threshold:
        action = "buy"
    elif conviction < avoid_threshold:
        action = "avoid"
    else:
        action = "watch"

    reason = _build_reason(factor_scores_by_name, weighted_values)
    valid_until = _compute_valid_until(analysis, run_date, config)

    factor_reasoning = {
        name: score.reasoning
        for name, score in factor_scores_by_name.items()
        if score.reasoning
    }
    return TickerDecision(
        ticker=analysis.ticker,
        action=action,
        conviction=conviction,
        reason=reason,
        valid_until=valid_until,
        factors=factors,
        factor_reasoning=factor_reasoning,
    )


def _build_reason(factor_scores_by_name: dict[str, FactorScore], weighted_values: dict[str, float]) -> str:
    ranked = sorted(
        factor_scores_by_name.items(),
        key=lambda item: abs(weighted_values.get(item[0], item[1].value)),
        reverse=True,
    )
    parts = [
        score.reasoning
        for factor_name, score in ranked[:3]
        if abs(weighted_values.get(factor_name, score.value)) >= 1 and score.reasoning
    ]
    return " / ".join(parts) if parts else "판단 근거 부족"


def _compute_valid_until(analysis: TickerAnalysis, run_date: date, config: dict[str, Any]) -> str:
    vu_config = config.get("valid_until", {})
    earnings_window = vu_config.get("earnings_window_days", 30)
    default_days = vu_config.get("default_days", 7)

    for event in analysis.upcoming_events:
        if event.get("type") == "earnings":
            try:
                days_until = int(float(str(event.get("days_until", ""))))
            except ValueError:
                days_until = None
            if days_until is not None and days_until <= earnings_window:
                event_date = event.get("date")
                if event_date:
                    return str(event_date)

    return (run_date + timedelta(days=default_days)).isoformat()


def _load_weights() -> dict[str, Any]:
    if _WEIGHTS_PATH.exists():
        try:
            with _WEIGHTS_PATH.open("r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
        except Exception:
            logger.warning("Failed to load decision weights, using defaults")
            config = {}
    else:
        config = {}

    merged = {
        "factors": {**_DEFAULT_FACTORS, **config.get("factors", {})},
        "regime_multipliers": {**_DEFAULT_REGIME_MULTIPLIERS, **config.get("regime_multipliers", {})},
        "thresholds": {**_DEFAULT_THRESHOLDS, **config.get("thresholds", {})},
        "valid_until": {**_DEFAULT_VALID_UNTIL, **config.get("valid_until", {})},
    }
    normalized = normalize_decision_config(merged)

    registry = build_factor_registry(normalized["factors"])
    scorer = ConvictionScorer(registry.all(), normalized["regime_multipliers"])
    normalized["_registry"] = registry
    normalized["_scorer"] = scorer
    return normalized
