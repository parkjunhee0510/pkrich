"""Technical indicator calculations from price history.

Computes RSI(14), MACD(12,26,9), and Bollinger Bands(20,2) from
a yfinance-style DataFrame with a 'Close' column. No external API
calls required — purely derived from existing history data.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from src.collector.helpers.formatters import (
    calculate_change_percent as _calculate_change_percent,
    coerce_finite_float as _coerce_finite_float,
)


def compute_technical_indicators(history: Any) -> dict[str, str]:
    """Compute RSI, MACD, and Bollinger Bands from price history.

    Args:
        history: pandas DataFrame with 'Close' column (6mo daily).

    Returns:
        Dict with keys like rsi_14, rsi_signal, macd, macd_signal, etc.
    """
    try:
        import pandas as pd
    except ImportError:
        return {}

    if not isinstance(history, pd.DataFrame) or history.empty:
        return {}

    close = history["Close"].dropna()
    if len(close) < 30:
        return {}

    result: dict[str, str] = {}

    # ── RSI(14) ────────────────────────────────────────────────────
    rsi = _calc_rsi(close, 14)
    if rsi is not None:
        result["rsi_14"] = f"{rsi:.1f}"
        if rsi >= 70:
            result["rsi_signal"] = "overbought"
        elif rsi <= 30:
            result["rsi_signal"] = "oversold"
        else:
            result["rsi_signal"] = "neutral"

    # ── MACD(12, 26, 9) ───────────────────────────────────────────
    macd_line, signal_line, histogram = _calc_macd(close, 12, 26, 9)
    if macd_line is not None and signal_line is not None:
        result["macd"] = f"{macd_line:.2f}"
        result["macd_signal"] = f"{signal_line:.2f}"
        result["macd_histogram"] = f"{histogram:.2f}"
        if macd_line > signal_line and histogram > 0:
            result["macd_crossover"] = "bullish"
        elif macd_line < signal_line and histogram < 0:
            result["macd_crossover"] = "bearish"
        else:
            result["macd_crossover"] = "neutral"

    # ── Bollinger Bands(20, 2) ─────────────────────────────────────
    bb_upper, bb_middle, bb_lower = _calc_bollinger_bands(close, 20, 2)
    if bb_upper is not None:
        result["bb_upper"] = f"{bb_upper:.2f}"
        result["bb_middle"] = f"{bb_middle:.2f}"
        result["bb_lower"] = f"{bb_lower:.2f}"
        latest_price = float(close.iloc[-1])
        bandwidth = (bb_upper - bb_lower) / bb_middle * 100 if bb_middle else 0
        result["bb_bandwidth"] = f"{bandwidth:.1f}%"
        if latest_price >= bb_upper:
            result["bb_position"] = "upper_band"
        elif latest_price >= bb_middle + (bb_upper - bb_middle) / 2:
            result["bb_position"] = "upper_half"
        elif latest_price >= bb_middle:
            result["bb_position"] = "middle"
        elif latest_price >= bb_lower + (bb_middle - bb_lower) / 2:
            result["bb_position"] = "lower_half"
        else:
            result["bb_position"] = "lower_band"

    return result


def _calc_rsi(close: Any, period: int = 14) -> float | None:
    """Wilder smoothing RSI."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.iloc[1:period + 1].mean()
    avg_loss = loss.iloc[1:period + 1].mean()

    if avg_gain == 0 and avg_loss == 0:
        return 50.0

    for i in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + float(gain.iloc[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(loss.iloc[i])) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _calc_macd(
    close: Any, fast: int = 12, slow: int = 26, signal_period: int = 9
) -> tuple[float | None, float | None, float | None]:
    """MACD line, signal line, histogram."""
    if len(close) < slow + signal_period:
        return None, None, None
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


def _calc_bollinger_bands(
    close: Any, period: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    """Upper, middle, lower Bollinger Bands."""
    if len(close) < period:
        return None, None, None
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return float(upper.iloc[-1]), float(sma.iloc[-1]), float(lower.iloc[-1])


# ---------------------------------------------------------------------------
# Calculation helpers moved from price.py (Step 5b migration)
# ---------------------------------------------------------------------------

def _extract_history_values(history: object, column_name: str) -> list[float | None]:
    if getattr(history, "empty", True):
        return []
    try:
        column = history[column_name]
    except Exception:
        return []
    try:
        values = list(column)
    except TypeError:
        values = column if isinstance(column, list) else []
    return [_coerce_finite_float(value) for value in values]


def _calc_atr_14d(history: object) -> float | None:
    highs = _extract_history_values(history, "High")
    lows = _extract_history_values(history, "Low")
    closes = _extract_history_values(history, "Close")
    if not highs or not lows or not closes:
        return None

    length = min(len(highs), len(lows), len(closes))
    true_ranges: list[float] = []
    previous_close: float | None = None
    for index in range(length):
        high = highs[index]
        low = lows[index]
        close = closes[index]
        if high is None or low is None or close is None:
            previous_close = close if close is not None else previous_close
            continue
        intraday_range = high - low
        if previous_close is None:
            true_range = intraday_range
        else:
            true_range = max(
                intraday_range,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = close

    if len(true_ranges) < 14:
        return None
    trailing_ranges = true_ranges[-14:]
    return sum(trailing_ranges) / len(trailing_ranges)


def _calc_atr_display(history: object, current_price: float | None) -> tuple[str, str]:
    atr_value = _calc_atr_14d(history)
    if atr_value is None:
        return "N/A", "N/A"
    atr_percent = _calculate_change_percent(atr_value, current_price)
    if current_price and current_price != 0:
        atr_percent = (atr_value / current_price) * 100
    return f"{atr_value:.2f}", f"{atr_percent:.2f}%" if atr_percent is not None else "N/A"


def _calc_relative_volume(info: dict[str, Any]) -> str:
    current_volume = _coerce_finite_float(info.get("volume"))
    average_volume = _coerce_finite_float(info.get("averageVolume")) or _coerce_finite_float(info.get("averageVolume10days"))
    if current_volume is None or average_volume is None or average_volume == 0:
        return "N/A"
    return f"{current_volume / average_volume:.2f}x"


def _calc_gap_percent(open_price: float | None, previous_close: float | None) -> str:
    gap = _calculate_change_percent(open_price, previous_close) if open_price is not None else None
    if gap is None:
        return "N/A"
    return f"{gap:+.2f}%"


def _calc_price_vs_sma(price: float | None, sma: float | None) -> str:
    change = _calculate_change_percent(price, sma) if price is not None else None
    if change is None:
        return "N/A"
    return f"{change:+.2f}%"


def _calc_week52_position(price: float | None, week52_high: float | None, week52_low: float | None) -> str:
    if price is None or week52_high is None or week52_low is None or week52_high <= week52_low:
        return "N/A"
    position = ((price - week52_low) / (week52_high - week52_low)) * 100
    return f"{position:.0f}%"


def _parse_percent_value(value: "str | float | None") -> float | None:
    import math
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        return numeric_value if math.isfinite(numeric_value) else None
    text = str(value).strip()
    if not text or text == "N/A":
        return None
    if text.endswith("%"):
        text = text[:-1]
    return _coerce_finite_float(text)


def _calc_rs_vs_benchmark(price_change_30d: str, benchmark_change_30d: float | None) -> str:
    ticker_change = _parse_percent_value(price_change_30d)
    if ticker_change is None or benchmark_change_30d is None:
        return "N/A"
    return f"{(ticker_change - benchmark_change_30d):+.2f}%"


def _calculate_history_period_change(history: object, current_price: float, run_date: date, days: int) -> float | None:
    target = run_date - timedelta(days=days)
    if getattr(history, "empty", True):
        return None
    try:
        close_col = history["Close"]
        index = history.index
    except Exception:
        return None

    anchor: float | None = None
    for idx_val, close_val in zip(index, close_col):
        try:
            row_date = idx_val.date() if hasattr(idx_val, "date") else date.fromisoformat(str(idx_val)[:10])
        except Exception:
            continue
        if row_date <= target:
            normalized_close = _coerce_finite_float(close_val)
            if normalized_close is not None:
                anchor = normalized_close
    return _calculate_change_percent(current_price, anchor)


def _format_period_change(history: object, current_price: float, run_date: date, days: int) -> str:
    period_change = _calculate_history_period_change(history, current_price, run_date, days)
    if period_change is None:
        return "N/A"
    return f"{period_change:+.2f}%"
