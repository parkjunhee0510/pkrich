from __future__ import annotations

import re

from src.types import CollectedTickerData, WatchlistItem

_CONDITION_PATTERN = re.compile(r"^\s*(price|change_percent)\s*(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")


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
    current_value = market.price if field == "price" else market.change_percent
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
