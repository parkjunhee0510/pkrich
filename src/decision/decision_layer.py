"""Per-ticker decision layer with plugin-based factor scoring."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.decision.base import FactorScore
from src.decision.config import multiplier_for, normalize_decision_config
from src.decision.registry import build_factor_registry
from src.decision.scorer import ConvictionScorer
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path("config/decision_weights.yaml")
_DEFAULT_FACTORS = {
    "valuation": {"min": -12, "max": 12},
    "momentum": {"min": -12, "max": 12},
    "catalyst_recency": {"min": -10, "max": 20},
    "signal_track_record": {"min": -10, "max": 10},
    "news_tone": {"min": -5, "max": 10},
    "regime_adjustment": {"min": -6, "max": 6},
    "earnings_pattern": {"min": -10, "max": 10},
    "fundamentals": {"min": -6, "max": 6},
    "portfolio_risk": {"min": -10, "max": 0},
}
_DEFAULT_THRESHOLDS = {"buy": 65, "buy_risk_off": 75, "avoid": 35}
_DEFAULT_VALID_UNTIL = {"earnings_window_days": 30, "default_days": 7}
_DEFAULT_REGIME_MULTIPLIERS = {"risk_on": {}, "risk_off": {}, "neutral": {}}


def generate_decisions(
    analyses: list[TickerAnalysis],
    collected: dict[str, CollectedTickerData] | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any] | None,
    run_date: date,
    *,
    portfolio_risk: dict[str, Any] | None = None,
) -> list[TickerDecision]:
    try:
        config = _load_weights()
        collected = collected or {}
        signal_stats = signal_stats or {}
        decision_context = {**signal_stats, "_portfolio_risk": portfolio_risk or {}}
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
    diagnostics = _evaluate_ticker(
        analysis,
        data,
        regime,
        signal_stats,
        config,
    )

    reason = _build_reason(diagnostics["factor_scores_by_name"], diagnostics["weighted_values"])
    valid_until = _compute_valid_until(analysis, run_date, config)

    return TickerDecision(
        ticker=analysis.ticker,
        action=diagnostics["action"],
        conviction=diagnostics["conviction"],
        reason=reason,
        valid_until=valid_until,
        factors=diagnostics["factors"],
    )


def build_decision_diagnostics(
    analyses: list[TickerAnalysis],
    collected: dict[str, CollectedTickerData] | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    config = _load_weights()
    collected = collected or {}
    signal_stats = signal_stats or {}
    decision_context = {**signal_stats}
    rows: list[dict[str, Any]] = []

    for analysis in analyses:
        diagnostics = _evaluate_ticker(
            analysis,
            collected.get(analysis.ticker),
            regime,
            decision_context,
            config,
        )
        rows.append(
            {
                "ticker": analysis.ticker,
                "action": diagnostics["action"],
                "conviction": diagnostics["conviction"],
                "factor_scores": diagnostics["factors"],
                "weighted_scores": diagnostics["weighted_values"],
                "regime_multipliers": diagnostics["regime_multipliers"],
                "threshold_band": diagnostics["threshold_band"],
            }
        )
    return rows


def print_factor_distribution(
    analyses: list[TickerAnalysis],
    collected: dict[str, CollectedTickerData] | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any] | None,
) -> None:
    rows = build_decision_diagnostics(analyses, collected, regime, signal_stats)
    for row in rows:
        print(
            yaml.safe_dump(
                row,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ).strip()
        )
        print("---")


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


def _evaluate_ticker(
    analysis: TickerAnalysis,
    data: CollectedTickerData | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    registry = config["_registry"]
    scorer = config["_scorer"]
    factor_scores_by_name: dict[str, FactorScore] = {}
    factors: dict[str, float] = {}
    regime_multipliers: dict[str, float] = {}

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
        regime_multipliers[factor.name] = multiplier_for(
            factor.name,
            regime.regime,
            config.get("regime_multipliers", {}),
        )

    weighted_values = scorer.weighted_values(factor_scores_by_name, regime.regime)
    conviction = scorer.calculate(factor_scores_by_name, regime.regime)
    buy_threshold, avoid_threshold = _resolve_thresholds(regime, config)
    action, threshold_band = _resolve_action_band(conviction, buy_threshold, avoid_threshold)

    return {
        "action": action,
        "conviction": conviction,
        "factors": factors,
        "factor_scores_by_name": factor_scores_by_name,
        "weighted_values": weighted_values,
        "regime_multipliers": regime_multipliers,
        "threshold_band": threshold_band,
    }


def _resolve_thresholds(regime: MarketRegime, config: dict[str, Any]) -> tuple[int, int]:
    thresholds = config.get("thresholds", {})
    buy_threshold = thresholds.get("buy_risk_off", 75) if regime.regime == "risk_off" else thresholds.get("buy", 65)
    avoid_threshold = thresholds.get("avoid", 35)
    return int(buy_threshold), int(avoid_threshold)


def _resolve_action_band(conviction: int, buy_threshold: int, avoid_threshold: int) -> tuple[str, str]:
    if conviction >= buy_threshold:
        return "buy", f"buy (>={buy_threshold})"
    if conviction < avoid_threshold:
        return "avoid", f"avoid (<{avoid_threshold})"
    return "watch", f"watch ({avoid_threshold}-{buy_threshold - 1})"


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
