from __future__ import annotations

import re

from src.types import CollectedTickerData, WatchlistItem

_CONDITION_PATTERN = re.compile(
    r"^\s*(price|change_percent|relative_volume|rsi|atr_percent|rs_vs_spy)\s*(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$"
)


def evaluate_alert_rules(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
) -> list[str]:
    alerts: list[str] = []
    for item in watchlist:
        market = collected.get(item.ticker)
        if market is None:
            continue
        for rule in item.alert_rules:
            condition = rule.get("condition", "")
            if _evaluate_condition(condition, market):
                alerts.append(f"{item.ticker}: {rule.get('message', condition)}")
    return alerts


def _evaluate_condition(condition: str, market: CollectedTickerData) -> bool:
    match = _CONDITION_PATTERN.match(condition)
    if not match:
        return False

    field, operator, raw_threshold = match.groups()
    threshold = float(raw_threshold)
    current_value = _resolve_numeric_field(field, market)
    if current_value is None:
        return False

    if operator == "<":
        return current_value < threshold
    if operator == "<=":
        return current_value <= threshold
    if operator == ">":
        return current_value > threshold
    if operator == ">=":
        return current_value >= threshold
    return False


def _resolve_numeric_field(field: str, market: CollectedTickerData) -> float | None:
    if field == "price":
        return market.price
    if field == "change_percent":
        return market.change_percent
    if field == "relative_volume":
        return _parse_numeric_text(market.relative_volume)
    if field == "atr_percent":
        return _parse_numeric_text(market.atr_percent)
    if field == "rs_vs_spy":
        return _parse_numeric_text(market.rs_vs_spy)
    if field == "rsi":
        return _parse_numeric_text(market.technical_indicators.get("rsi_14", "N/A"))
    return None


def _parse_numeric_text(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
