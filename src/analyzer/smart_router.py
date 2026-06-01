"""Deterministic priority scoring for ensemble deep-review routing."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.types import CollectedTickerData, TickerAnalysis, TickerDecision, WatchlistItem
from src.utils.budget_guard import estimate_profile_call_cost
from src.utils.model_config import ModelProfile


BOUNDARY_REASON = "uncertainty_boundary"
PORTFOLIO_REASON = "portfolio_exposure"
EVENT_REASON = "event_proximity"
EVIDENCE_GAP_REASON = "evidence_gap"
VOLATILITY_REASON = "volatility"
SIGNAL_IMPORTANCE_REASON = "signal_importance"


def build_router_scores(
    watchlist: list[WatchlistItem],
    decision_map: dict[str, TickerDecision],
    *,
    analyses_by_ticker: dict[str, TickerAnalysis] | None = None,
    collected_by_ticker: dict[str, CollectedTickerData] | None = None,
    portfolio_tickers: set[str] | None = None,
    run_date: date | None = None,
) -> dict[str, dict[str, object]]:
    analyses_by_ticker = analyses_by_ticker or {}
    collected_by_ticker = collected_by_ticker or {}
    portfolio_tickers = portfolio_tickers or set()
    scores: dict[str, dict[str, object]] = {}
    for item in watchlist:
        ticker = item.ticker
        decision = decision_map.get(ticker)
        analysis = analyses_by_ticker.get(ticker)
        collected = collected_by_ticker.get(ticker)
        components = {
            BOUNDARY_REASON: _boundary_proximity_score(decision),
            PORTFOLIO_REASON: 30.0 if ticker in portfolio_tickers else 0.0,
            EVENT_REASON: 15.0 if _has_near_event(analysis, collected, run_date=run_date) else 0.0,
            EVIDENCE_GAP_REASON: _evidence_gap_score(decision),
            VOLATILITY_REASON: _volatility_score(collected),
            SIGNAL_IMPORTANCE_REASON: 10.0 if decision and decision.action in {"buy", "avoid"} else 0.0,
        }
        reason_codes = [name for name, value in components.items() if value > 0]
        priority_score = round(sum(components.values()), 3)
        scores[ticker] = {
            "ticker": ticker,
            "priority_score": priority_score,
            "reason_codes": reason_codes,
            "components": {name: round(value, 3) for name, value in components.items() if value > 0},
        }
    return scores


def rank_router_candidates(
    candidate_tickers: list[str],
    router_scores: dict[str, dict[str, object]],
    watchlist: list[WatchlistItem],
) -> list[str]:
    watchlist_order = {item.ticker: index for index, item in enumerate(watchlist)}
    return sorted(
        candidate_tickers,
        key=lambda ticker: (
            -float(router_scores.get(ticker, {}).get("priority_score", 0.0) or 0.0),
            watchlist_order.get(ticker, 9999),
        ),
    )


def estimate_deep_review_cost(
    profile: ModelProfile,
    *,
    selected_count: int,
    trading_days_per_month: int = 22,
    input_tokens_per_ticker: int = 6000,
    output_tokens_per_ticker: int = 4000,
) -> dict[str, object]:
    effective_count = max(0, int(selected_count or 0))
    incremental = estimate_profile_call_cost(
        input_tokens=effective_count * input_tokens_per_ticker,
        output_tokens=effective_count * min(profile.max_output_tokens, output_tokens_per_ticker),
        input_cost_per_1m=profile.input_cost_per_1m_tokens,
        output_cost_per_1m=profile.output_cost_per_1m_tokens,
    )
    return {
        "profile": profile.name,
        "model": profile.model,
        "selected_count": effective_count,
        "input_tokens_per_ticker": input_tokens_per_ticker,
        "output_tokens_per_ticker": min(profile.max_output_tokens, output_tokens_per_ticker),
        "estimated_incremental_cost_usd": incremental,
        "estimated_monthly_cost_usd": round(incremental * max(0, int(trading_days_per_month or 0)), 4),
        "trading_days_per_month": max(0, int(trading_days_per_month or 0)),
    }


def _boundary_proximity_score(decision: TickerDecision | None) -> float:
    if decision is None:
        return 0.0
    conviction = max(0, min(100, int(decision.conviction or 0)))
    nearest_boundary_distance = min(abs(conviction - 35), abs(conviction - 65))
    return max(0.0, 30.0 - (nearest_boundary_distance * 2.0))


def _evidence_gap_score(decision: TickerDecision | None) -> float:
    if decision is None:
        return 0.0
    meta = decision.confidence_meta or {}
    score = _float_or_none(meta.get("search_evidence_score"))
    gate = meta.get("search_quality_gate")
    would_cap = isinstance(gate, dict) and bool(gate.get("would_cap_action"))
    if would_cap:
        return 15.0
    if score is None:
        return 0.0
    if score >= 0.55:
        return 0.0
    return round((0.55 - max(0.0, score)) / 0.55 * 15.0, 3)


def _volatility_score(collected: CollectedTickerData | None) -> float:
    if collected is None:
        return 0.0
    change = _float_or_none(collected.change_percent)
    if change is None:
        return 0.0
    magnitude = abs(change)
    if magnitude < 5.0:
        return 0.0
    return round(min(10.0, magnitude), 3)


def _has_near_event(
    analysis: TickerAnalysis | None,
    collected: CollectedTickerData | None,
    *,
    run_date: date | None,
) -> bool:
    events: list[dict[str, Any]] = []
    if analysis is not None:
        events.extend(analysis.upcoming_events or [])
    if collected is not None:
        events.extend(collected.upcoming_events or [])
    for event in events:
        days_until = _int_or_none(event.get("days_until"))
        if days_until is not None and 0 <= days_until <= 14:
            return True
        event_date = _parse_event_date(event)
        if event_date is not None and run_date is not None:
            delta = (event_date - run_date).days
            if 0 <= delta <= 14:
                return True
    return False


def _parse_event_date(event: dict[str, Any]) -> date | None:
    for key in ("date", "event_date", "earnings_date", "ex_date"):
        value = str(event.get(key, "")).strip()
        if not value:
            continue
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            continue
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
