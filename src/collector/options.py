from __future__ import annotations

import math
from statistics import median
from typing import Any


def collect_options_summary(ticker_symbol: str) -> dict[str, str]:
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return {}

    try:
        ticker = yf.Ticker(ticker_symbol)
        expirations = list(getattr(ticker, "options", []) or [])
        if not expirations:
            return {}

        expiry = expirations[0]
        option_chain = ticker.option_chain(expiry)
        calls = getattr(option_chain, "calls", None)
        puts = getattr(option_chain, "puts", None)
        if calls is None or puts is None or len(calls) == 0 or len(puts) == 0:
            return {}

        calls_records = calls.to_dict("records")
        puts_records = puts.to_dict("records")
        if not calls_records or not puts_records:
            return {}

        underlying_price = _extract_underlying_price(ticker)
        call_iv = _pick_atm_iv(calls_records, underlying_price)
        put_iv = _pick_atm_iv(puts_records, underlying_price)
        total_call_oi = sum(_coerce_float(item.get("openInterest")) or 0.0 for item in calls_records)
        total_put_oi = sum(_coerce_float(item.get("openInterest")) or 0.0 for item in puts_records)
        put_call_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else None
        iv_percentile = _estimate_iv_percentile(calls_records, puts_records, call_iv, put_iv)

        summary = {
            "expiry": str(expiry),
            "atm_call_iv": _format_percent(call_iv),
            "atm_put_iv": _format_percent(put_iv),
            "put_call_ratio": _format_ratio(put_call_ratio),
            "iv_percentile_30d": _format_percentile(iv_percentile),
        }
        return {key: value for key, value in summary.items() if value != "N/A"}
    except Exception:
        return {}


def _extract_underlying_price(ticker: Any) -> float | None:
    info = getattr(ticker, "info", {}) or {}
    for key in ("regularMarketPrice", "currentPrice", "previousClose"):
        value = _coerce_float(info.get(key))
        if value and value > 0:
            return value
    return None


def _pick_atm_iv(records: list[dict[str, Any]], underlying_price: float | None) -> float | None:
    if not records:
        return None
    if underlying_price is None:
        vols = [_coerce_float(item.get("impliedVolatility")) for item in records]
        clean = [value for value in vols if value is not None]
        return median(clean) if clean else None

    ranked = sorted(
        records,
        key=lambda item: abs((_coerce_float(item.get("strike")) or underlying_price) - underlying_price),
    )
    for item in ranked[:5]:
        iv = _coerce_float(item.get("impliedVolatility"))
        if iv is not None:
            return iv
    return None


def _estimate_iv_percentile(
    calls_records: list[dict[str, Any]],
    puts_records: list[dict[str, Any]],
    call_iv: float | None,
    put_iv: float | None,
) -> float | None:
    current_iv_candidates = [value for value in (call_iv, put_iv) if value is not None]
    if not current_iv_candidates:
        return None
    current_iv = sum(current_iv_candidates) / len(current_iv_candidates)

    universe = [
        _coerce_float(item.get("impliedVolatility"))
        for item in [*calls_records, *puts_records]
    ]
    valid = sorted(value for value in universe if value is not None)
    if len(valid) < 5:
        return None
    less_or_equal = sum(1 for value in valid if value <= current_iv)
    return (less_or_equal / len(valid)) * 100


def _coerce_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _format_percentile(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.0f}th"


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}x"
