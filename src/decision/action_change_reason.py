"""Deterministic action-change explanation helpers."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from src.types import MarketRegime, TickerDecision

BUY_THRESHOLD = 65
AVOID_THRESHOLD = 35
DATA_QUALITY_MOVE_THRESHOLD = 0.10
_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def build_action_change_reasons(
    decisions: list[TickerDecision],
    signal_rows: list[dict[str, str]],
    *,
    run_date: date,
    market_regime: MarketRegime,
) -> list[dict[str, Any]]:
    """Compare current decisions with the latest prior tracked signal rows."""
    previous_by_ticker = _latest_previous_rows(signal_rows, run_date=run_date)
    current_regime = str(getattr(market_regime, "regime", "") or "unknown").strip() or "unknown"
    results: list[dict[str, Any]] = []

    for decision in sorted(decisions, key=lambda item: item.ticker):
        ticker = decision.ticker.strip().upper()
        previous = previous_by_ticker.get(ticker)
        if previous is None:
            results.append(
                {
                    "ticker": ticker,
                    "previous_action": "",
                    "current_action": decision.action,
                    "previous_conviction": None,
                    "current_conviction": decision.conviction,
                    "previous_regime": "",
                    "current_regime": current_regime,
                    "reason_codes": ["new_ticker", "insufficient_previous_snapshot"],
                    "summary": f"{ticker} is new in the tracked decision history.",
                    "contributors": [],
                }
            )
            continue

        previous_action = str(previous.get("action", "") or "watch").strip().lower() or "watch"
        previous_conviction = _parse_float(previous.get("conviction"))
        previous_regime = str(previous.get("regime", "") or "unknown").strip() or "unknown"
        reason_codes = _reason_codes(
            previous_action=previous_action,
            current_action=decision.action,
            previous_conviction=previous_conviction,
            current_conviction=float(decision.conviction),
            previous_regime=previous_regime,
            current_regime=current_regime,
            previous_data_quality=_previous_data_quality(previous),
            current_data_quality=_current_data_quality(decision),
            previous_factors=_parse_json_object(previous.get("factors_json")),
            current_factors=decision.factors,
        )
        results.append(
            {
                "ticker": ticker,
                "previous_action": previous_action,
                "current_action": decision.action,
                "previous_conviction": previous_conviction,
                "current_conviction": decision.conviction,
                "previous_regime": previous_regime,
                "current_regime": current_regime,
                "reason_codes": reason_codes,
                "summary": _summary(ticker, previous_action, decision.action, reason_codes),
                "contributors": _contributors(previous, decision),
            }
        )
    return results


def _latest_previous_rows(
    signal_rows: list[dict[str, str]],
    *,
    run_date: date,
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in sorted(signal_rows, key=lambda item: (item.get("signal_date", ""), item.get("ticker", ""))):
        ticker = str(row.get("ticker", "")).strip().upper()
        row_date = _parse_date(row.get("signal_date"))
        if not ticker or row_date is None or row_date >= run_date:
            continue
        result[ticker] = row
    return result


def _reason_codes(
    *,
    previous_action: str,
    current_action: str,
    previous_conviction: float | None,
    current_conviction: float,
    previous_regime: str,
    current_regime: str,
    previous_data_quality: float | None,
    current_data_quality: float | None,
    previous_factors: dict[str, Any],
    current_factors: dict[str, float],
) -> list[str]:
    codes: list[str] = []
    normalized_current_action = str(current_action or "watch").strip().lower() or "watch"
    if previous_action == normalized_current_action:
        codes.append("action_unchanged")
    elif _action_rank(normalized_current_action) > _action_rank(previous_action):
        codes.append("action_upgraded")
    else:
        codes.append("action_downgraded")

    if previous_conviction is not None:
        if current_conviction > previous_conviction:
            codes.append("conviction_increased")
        elif current_conviction < previous_conviction:
            codes.append("conviction_decreased")
        if previous_conviction < BUY_THRESHOLD <= current_conviction:
            codes.append("conviction_crossed_buy_threshold")
        if previous_conviction >= BUY_THRESHOLD > current_conviction:
            codes.append("conviction_fell_below_buy_threshold")
        if previous_conviction > AVOID_THRESHOLD >= current_conviction:
            codes.append("conviction_crossed_avoid_threshold")
        if previous_conviction <= AVOID_THRESHOLD < current_conviction:
            codes.append("conviction_recovered_from_avoid_threshold")

    if previous_regime != current_regime:
        codes.append("macro_regime_changed")
    if _top_factor(previous_factors) != _top_factor(current_factors):
        codes.append("top_factor_changed")
    if previous_data_quality is not None and current_data_quality is not None:
        delta = current_data_quality - previous_data_quality
        if delta >= DATA_QUALITY_MOVE_THRESHOLD:
            codes.append("data_quality_improved")
        elif delta <= -DATA_QUALITY_MOVE_THRESHOLD:
            codes.append("data_quality_deteriorated")
    return codes


def _action_rank(action: str) -> int:
    return {"avoid": 0, "watch": 1, "buy": 2}.get(action, 1)


def _summary(ticker: str, previous_action: str, current_action: str, codes: list[str]) -> str:
    if previous_action == current_action:
        return f"{ticker} stayed {current_action}; main changes: {', '.join(codes)}."
    return f"{ticker} changed {previous_action} -> {current_action}; main changes: {', '.join(codes)}."


def _contributors(previous: dict[str, str], decision: TickerDecision) -> list[dict[str, Any]]:
    previous_factors = _parse_json_object(previous.get("factors_json"))
    names = sorted(set(previous_factors) | set(decision.factors))
    return [
        {
            "factor": name,
            "previous": _coerce_float(previous_factors.get(name)),
            "current": _coerce_float(decision.factors.get(name)),
        }
        for name in names
    ]


def _top_factor(factors: dict[str, Any]) -> str:
    numeric = {
        name: abs(value)
        for name, value in ((key, _coerce_float(raw_value)) for key, raw_value in factors.items())
        if value is not None
    }
    if not numeric:
        return ""
    return max(sorted(numeric), key=lambda name: numeric[name])


def _previous_data_quality(row: dict[str, str]) -> float | None:
    payload = _parse_json_object(row.get("confidence_meta_json"))
    return _coerce_float(payload.get("data_quality_score"))


def _current_data_quality(decision: TickerDecision) -> float | None:
    return _coerce_float(decision.confidence_meta.get("data_quality_score"))


def _parse_json_object(raw: object) -> dict[str, Any]:
    try:
        payload = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_date(raw: object) -> date | None:
    try:
        return date.fromisoformat(str(raw or ""))
    except ValueError:
        return None


def _parse_float(raw: object) -> float | None:
    text = str(raw or "").strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    return _coerce_float(match.group(0).replace(",", ""))


def _coerce_float(raw: object) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
