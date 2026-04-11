"""Technical indicator calculations from price history.

Computes RSI(14), MACD(12,26,9), and Bollinger Bands(20,2) from
a yfinance-style DataFrame with a 'Close' column. No external API
calls required — purely derived from existing history data.
"""

from __future__ import annotations

from typing import Any


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
