from __future__ import annotations

import json
import math
from datetime import date
from typing import Any

from src.types import MarketRegime, TickerDecision


BUY_THRESHOLD = 65
BUY_RISK_OFF_THRESHOLD = 75
AVOID_THRESHOLD = 35
DATA_QUALITY_MOVE_THRESHOLD = 0.10

_ACTION_RANK = {
    "avoid": 0,
    "watch": 1,
    "buy": 2,
}


def build_action_change_reasons(
    decisions: list[TickerDecision],
    signal_rows: list[dict[str, str]],
    *,
    run_date: date,
    market_regime: MarketRegime,
) -> list[dict[str, Any]]:
    """Build deterministic explanation metadata for ticker action changes."""

    previous_by_ticker = _latest_previous_rows(signal_rows, run_date)
    current_regime = _clean_str(getattr(market_regime, "regime", ""))
    buy_threshold = _buy_threshold_for_regime(current_regime)
    results: list[dict[str, Any]] = []

    for decision in sorted(decisions, key=lambda item: _clean_str(item.ticker).upper()):
        ticker = _clean_str(decision.ticker).upper()
        previous = previous_by_ticker.get(ticker)
        current_action = _clean_str(decision.action)
        current_conviction = _parse_float(decision.conviction)
        current_factors = _coerce_factor_map(decision.factors)
        current_data_quality = _parse_float(decision.confidence_meta.get("data_quality_score"))
        current_top_factor = _top_factor(current_factors)

        if previous is None:
            reason_codes = ["new_ticker", "insufficient_previous_snapshot"]
            contributors = _build_contributors({}, current_factors)
            results.append(
                {
                    "ticker": ticker,
                    "run_date": run_date.isoformat(),
                    "previous_signal_date": None,
                    "previous_action": None,
                    "current_action": current_action,
                    "previous_conviction": None,
                    "current_conviction": current_conviction,
                    "previous_regime": None,
                    "current_regime": current_regime,
                    "previous_data_quality_score": None,
                    "current_data_quality_score": current_data_quality,
                    "previous_top_factor": None,
                    "current_top_factor": current_top_factor,
                    "reason_codes": reason_codes,
                    "contributors": contributors,
                    "summary": _build_summary(ticker, None, current_action, reason_codes),
                }
            )
            continue

        previous_action = _clean_str(previous.get("action", ""))
        previous_conviction = _parse_float(previous.get("conviction"))
        previous_regime = _clean_str(previous.get("regime", ""))
        previous_factors = _parse_json_mapping(previous.get("factors_json"))
        previous_data_quality = _parse_float(
            _parse_json_mapping(previous.get("confidence_meta_json")).get("data_quality_score")
        )
        previous_top_factor = _top_factor(previous_factors)

        reason_codes = _build_reason_codes(
            previous_action=previous_action,
            current_action=current_action,
            previous_conviction=previous_conviction,
            current_conviction=current_conviction,
            previous_regime=previous_regime,
            current_regime=current_regime,
            previous_data_quality=previous_data_quality,
            current_data_quality=current_data_quality,
            previous_top_factor=previous_top_factor,
            current_top_factor=current_top_factor,
            buy_threshold=buy_threshold,
        )

        results.append(
            {
                "ticker": ticker,
                "run_date": run_date.isoformat(),
                "previous_signal_date": previous.get("signal_date"),
                "previous_action": previous_action,
                "current_action": current_action,
                "previous_conviction": previous_conviction,
                "current_conviction": current_conviction,
                "previous_regime": previous_regime,
                "current_regime": current_regime,
                "previous_data_quality_score": previous_data_quality,
                "current_data_quality_score": current_data_quality,
                "previous_top_factor": previous_top_factor,
                "current_top_factor": current_top_factor,
                "reason_codes": reason_codes,
                "contributors": _build_contributors(previous_factors, current_factors),
                "summary": _build_summary(ticker, previous_action, current_action, reason_codes),
            }
        )

    return results


def _latest_previous_rows(signal_rows: list[dict[str, str]], run_date: date) -> dict[str, dict[str, str]]:
    latest: dict[str, tuple[date, int, dict[str, str]]] = {}

    for index, row in enumerate(signal_rows):
        ticker = _clean_str(row.get("ticker", "")).upper()
        signal_date = _parse_date(row.get("signal_date"))
        if not ticker or signal_date is None or signal_date >= run_date:
            continue
        previous = latest.get(ticker)
        if previous is None or (signal_date, index) > (previous[0], previous[1]):
            latest[ticker] = (signal_date, index, row)

    return {ticker: row for ticker, (_, _, row) in latest.items()}


def _build_reason_codes(
    *,
    previous_action: str,
    current_action: str,
    previous_conviction: float | None,
    current_conviction: float | None,
    previous_regime: str,
    current_regime: str,
    previous_data_quality: float | None,
    current_data_quality: float | None,
    previous_top_factor: str | None,
    current_top_factor: str | None,
    buy_threshold: int,
) -> list[str]:
    reason_codes: list[str] = []

    previous_rank = _ACTION_RANK.get(previous_action)
    current_rank = _ACTION_RANK.get(current_action)
    if previous_rank is None or current_rank is None:
        reason_codes.append("insufficient_previous_snapshot")
    elif previous_rank == current_rank:
        reason_codes.append("action_unchanged")
    elif current_rank > previous_rank:
        reason_codes.append("action_upgraded")
    else:
        reason_codes.append("action_downgraded")

    if previous_conviction is None or current_conviction is None:
        if "insufficient_previous_snapshot" not in reason_codes:
            reason_codes.append("insufficient_previous_snapshot")
    else:
        if current_conviction > previous_conviction:
            reason_codes.append("conviction_increased")
        elif current_conviction < previous_conviction:
            reason_codes.append("conviction_decreased")

        if previous_conviction < buy_threshold <= current_conviction:
            reason_codes.append("conviction_crossed_buy_threshold")
        if previous_conviction >= buy_threshold > current_conviction:
            reason_codes.append("conviction_fell_below_buy_threshold")
        if previous_conviction >= AVOID_THRESHOLD > current_conviction:
            reason_codes.append("conviction_crossed_avoid_threshold")
        if previous_conviction < AVOID_THRESHOLD <= current_conviction:
            reason_codes.append("conviction_recovered_from_avoid_threshold")

    if previous_regime and current_regime and previous_regime != current_regime:
        reason_codes.append("macro_regime_changed")

    if (
        previous_top_factor is not None
        and current_top_factor is not None
        and previous_top_factor != current_top_factor
    ):
        reason_codes.append("top_factor_changed")

    if previous_data_quality is None or current_data_quality is None:
        if "insufficient_previous_snapshot" not in reason_codes:
            reason_codes.append("insufficient_previous_snapshot")
    else:
        data_quality_delta = current_data_quality - previous_data_quality
        if data_quality_delta >= DATA_QUALITY_MOVE_THRESHOLD:
            reason_codes.append("data_quality_improved")
        elif data_quality_delta <= -DATA_QUALITY_MOVE_THRESHOLD:
            reason_codes.append("data_quality_deteriorated")

    return reason_codes


def _buy_threshold_for_regime(regime: str) -> int:
    return BUY_RISK_OFF_THRESHOLD if regime == "risk_off" else BUY_THRESHOLD


def _build_contributors(
    previous_factors: dict[str, float],
    current_factors: dict[str, float],
) -> list[dict[str, Any]]:
    contributors: list[dict[str, Any]] = []
    for name in sorted(set(previous_factors) | set(current_factors)):
        contributors.append(
            {
                "factor": name,
                "previous_value": previous_factors.get(name),
                "current_value": current_factors.get(name),
            }
        )
    return contributors


def _build_summary(
    ticker: str,
    previous_action: str | None,
    current_action: str,
    reason_codes: list[str],
) -> str:
    if previous_action is None:
        return (
            f"{ticker} is newly tracked at {current_action or 'unknown'}; "
            "no prior signal snapshot was available."
        )

    reason_text = ", ".join(reason_codes) if reason_codes else "no material change"
    return f"{ticker} moved from {previous_action or 'unknown'} to {current_action or 'unknown'}: {reason_text}."


def _parse_json_mapping(raw: Any) -> dict[str, float]:
    if isinstance(raw, dict):
        return _coerce_factor_map(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return _coerce_factor_map(parsed)


def _coerce_factor_map(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    factors: dict[str, float] = {}
    for key, value in raw.items():
        name = _clean_str(key)
        parsed = _parse_float(value)
        if name and parsed is not None:
            factors[name] = parsed
    return factors


def _top_factor(factors: dict[str, float]) -> str | None:
    if not factors:
        return None
    return sorted(factors.items(), key=lambda item: (-abs(item[1]), item[0]))[0][0]


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _clean_str(value: Any) -> str:
    return str(value or "").strip().lower()
