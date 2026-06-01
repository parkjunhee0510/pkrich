"""Deterministic priority ordering for search evidence refresh candidates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

REASON_ROUTER_SELECTED = "router_selected"
REASON_NO_EVIDENCE = "no_evidence"
REASON_NOT_REFRESHED = "not_refreshed"
REASON_STALE_CACHE = "stale_cache"
REASON_PORTFOLIO_HOLDING = "portfolio_holding"
REASON_IMPORTANT_ACTION = "important_action"
REASON_HIGH_VOLATILITY = "high_volatility"

IMPORTANT_ACTIONS = {"buy", "avoid"}
HIGH_VOLATILITY_PERCENT = 5.0

_REASON_WEIGHTS = {
    REASON_NO_EVIDENCE: 100,
    REASON_NOT_REFRESHED: 95,
    REASON_STALE_CACHE: 60,
    REASON_PORTFOLIO_HOLDING: 25,
    REASON_IMPORTANT_ACTION: 20,
    REASON_HIGH_VOLATILITY: 10,
    REASON_ROUTER_SELECTED: 0,
}


@dataclass(frozen=True)
class PriorityRefreshPlan:
    priority_tickers: list[str]
    reasons_by_ticker: dict[str, list[str]]
    reason_counts: dict[str, int]


def build_priority_refresh_plan(
    *,
    tickers: Iterable[str],
    router_priority_tickers: Iterable[str],
    mode: str,
    cached_tickers: Iterable[str] | None = None,
    stale_cache_tickers: Iterable[str] | None = None,
    priority_context_by_ticker: Mapping[str, Mapping[str, Any]] | None = None,
) -> PriorityRefreshPlan:
    """Build an ordered refresh plan from router choices and evidence context."""
    allowed_tickers = set(_normalize_tickers(tickers))
    priority_pool = _normalize_priority_pool(router_priority_tickers, allowed_tickers)
    cached = set(_normalize_tickers(cached_tickers or ()))
    stale_cache = set(_normalize_tickers(stale_cache_tickers or ()))
    context_by_ticker = _normalize_context_by_ticker(priority_context_by_ticker or {})
    cache_mode = str(mode or "").strip().lower() == "cache"

    reasons_by_ticker: dict[str, list[str]] = {}
    router_order_by_ticker: dict[str, int] = {}
    score_by_ticker: dict[str, int] = {}

    for router_order, ticker in enumerate(priority_pool):
        reasons = [REASON_ROUTER_SELECTED]
        if ticker in stale_cache:
            reasons.append(REASON_STALE_CACHE)
        if ticker not in cached:
            reasons.append(REASON_NOT_REFRESHED if cache_mode else REASON_NO_EVIDENCE)

        context = context_by_ticker.get(ticker, {})
        if context.get("in_portfolio"):
            reasons.append(REASON_PORTFOLIO_HOLDING)
        if _is_important_action(context.get("action")):
            reasons.append(REASON_IMPORTANT_ACTION)
        if _is_high_volatility(context):
            reasons.append(REASON_HIGH_VOLATILITY)

        reasons_by_ticker[ticker] = reasons
        router_order_by_ticker[ticker] = router_order
        score_by_ticker[ticker] = sum(_REASON_WEIGHTS[reason] for reason in reasons)

    priority_tickers = sorted(
        priority_pool,
        key=lambda ticker: (-score_by_ticker[ticker], router_order_by_ticker[ticker]),
    )
    ordered_reasons_by_ticker = {ticker: reasons_by_ticker[ticker] for ticker in priority_tickers}
    reason_counts = Counter(reason for reasons in ordered_reasons_by_ticker.values() for reason in reasons)

    return PriorityRefreshPlan(
        priority_tickers=priority_tickers,
        reasons_by_ticker=ordered_reasons_by_ticker,
        reason_counts=dict(sorted(reason_counts.items())),
    )


def _normalize_priority_pool(values: Iterable[str], allowed_tickers: set[str]) -> list[str]:
    if isinstance(values, (set, frozenset)):
        normalized_values: Iterable[str] = sorted(_normalize_ticker(value) for value in values)
    else:
        normalized_values = (_normalize_ticker(value) for value in values)

    result: list[str] = []
    seen: set[str] = set()
    for ticker in normalized_values:
        if ticker and ticker in allowed_tickers and ticker not in seen:
            result.append(ticker)
            seen.add(ticker)
    return result


def _normalize_tickers(values: Iterable[str]) -> list[str]:
    return [ticker for ticker in (_normalize_ticker(value) for value in values) if ticker]


def _normalize_context_by_ticker(
    context_by_ticker: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    return {
        ticker: context
        for raw_ticker, context in context_by_ticker.items()
        if (ticker := _normalize_ticker(raw_ticker)) and isinstance(context, Mapping)
    }


def _normalize_ticker(ticker: object) -> str:
    return str(ticker or "").strip().upper()


def _is_important_action(action: object) -> bool:
    return str(action or "").strip().lower() in IMPORTANT_ACTIONS


def _is_high_volatility(context: Mapping[str, Any]) -> bool:
    return any(
        abs(value) >= HIGH_VOLATILITY_PERCENT
        for value in (
            _parse_percent(context.get("change_percent")),
            _parse_percent(context.get("atr_percent")),
        )
        if value is not None
    )


def _parse_percent(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().rstrip("%").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
