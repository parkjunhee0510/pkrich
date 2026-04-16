"""Pure formatters extracted from `src/collector/price.py`.

These functions were originally private helpers on the legacy god-module
(`price.py`, 1946 lines). Providers under `src/collector/providers/` had
grown to import them via `from src.collector import price as price_legacy`,
which creates a cycle once Phase 1-0e Step 5b retires the legacy path.

Moving them here:
  * Breaks the provider → legacy coupling (providers can import from
    `src.collector.helpers.formatters` which has no dependency on
    `price.py`).
  * Makes the contract explicit — these are pure transforms of API
    response values into display strings. No I/O, no side effects.
  * Leaves `price.py` able to re-export them during the transition
    so no third-party caller breaks.

All functions follow the same defensive pattern:
    _coerce_finite_float handles TypeError/ValueError/NaN/Inf → None
    top-level formatters return "N/A" on missing/invalid input

This matches the convention used across the codebase — "N/A" is the
sentinel all downstream markdown/JSON renderers understand.
"""
from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Core coercion
# ---------------------------------------------------------------------------
def coerce_finite_float(value: object) -> float | None:
    """Return value as a finite float, or None if non-numeric / NaN / Inf.

    This is the single gateway every formatter uses before doing math,
    so upstream API weirdness (strings like "N/A", pandas NaN, Decimal,
    None) can never crash a formatter.
    """
    try:
        numeric_value = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def calculate_change_percent(
    latest_price: float, baseline_price: float | None
) -> float | None:
    """% change from baseline → latest. None when baseline missing/zero."""
    if baseline_price is None or baseline_price == 0:
        return None
    return (latest_price - baseline_price) / baseline_price * 100


# ---------------------------------------------------------------------------
# Number / size formatters
# ---------------------------------------------------------------------------
def format_large_number(value: object) -> str:
    """Format a large absolute number with T/B/M suffix.

    Used for marketCap, volume, averageVolume. Below 1M uses thousands
    separator.
    """
    numeric_value = coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    if numeric_value >= 1_000_000_000_000:
        return f"{numeric_value / 1_000_000_000_000:.2f}T"
    if numeric_value >= 1_000_000_000:
        return f"{numeric_value / 1_000_000_000:.2f}B"
    if numeric_value >= 1_000_000:
        return f"{numeric_value / 1_000_000:.2f}M"
    return f"{numeric_value:,.0f}"


def format_ratio(value: object) -> str:
    """Two-decimal string. Used for P/E, EPS, SMA, 52W hi/lo."""
    numeric_value = coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{numeric_value:.2f}"


def format_short_ratio(value: object) -> str:
    """Days-to-cover, Korean suffix (일)."""
    formatted = format_ratio(value)
    if formatted == "N/A":
        return formatted
    return f"{formatted}일"


def format_price(value: object, currency: str) -> str:
    """Two-decimal + currency code. Empty currency is tolerated."""
    formatted = format_ratio(value)
    if formatted == "N/A":
        return formatted
    return f"{formatted} {currency}".strip()


def format_analyst_count(value: object) -> str:
    """Integer + Korean 명 suffix."""
    numeric_value = coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{int(numeric_value)}명"


def format_percent_ratio(value: object) -> str:
    """Format a ratio that may already be percentage points OR a decimal.

    Some providers return dividendYield as 0.0041 (→ 0.41%), others as
    0.41 (already percentage). Using abs < 0.2 as the heuristic
    distinguishes the two without adding a flag to every call site.
    """
    numeric_value = coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    if abs(numeric_value) < 0.2:
        numeric_value *= 100
    return f"{numeric_value:.2f}%"


def format_fractional_percent(value: object) -> str:
    """Always treat input as a fraction (0.1234 → 12.34%).

    Used when the API contract is clear that the value is always a
    decimal fraction: shortPercentOfFloat, heldPercentInsiders,
    heldPercentInstitutions, impliedVolatility.
    """
    numeric_value = coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    return f"{numeric_value * 100:.2f}%"


def format_growth_percentage(value: object) -> str:
    """Signed YoY growth with percentage sign and 'YoY' tag.

    Handles both decimal fraction (0.15 → +15.00% YoY) and already-
    percentage (15 → +15.00% YoY). Similar heuristic to
    format_percent_ratio but tuned for growth values.
    """
    numeric_value = coerce_finite_float(value)
    if numeric_value is None:
        return "N/A"
    if abs(numeric_value) < 1:
        numeric_value *= 100
    return f"{numeric_value:+.2f}% YoY"


# ---------------------------------------------------------------------------
# Domain-specific formatters
# ---------------------------------------------------------------------------
def map_recommendation(score: float | None) -> str:
    """yfinance recommendationMean → Strong Buy / Buy / Hold / Sell / Strong Sell.

    yfinance encodes recommendations as 1.0 (Strong Buy) through 5.0
    (Strong Sell). The score is typically a mean across analysts so it
    lands between integers; we bucket at the midpoints.
    """
    if score is None:
        return "N/A"
    if score <= 1.5:
        return "Strong Buy"
    if score <= 2.5:
        return "Buy"
    if score <= 3.5:
        return "Hold"
    if score <= 4.5:
        return "Sell"
    return "Strong Sell"


def derive_forward_eps(price: float | None, forward_pe: object) -> str:
    """forward_eps = price / forwardPE. Used as a fallback when the API
    didn't provide forwardEps directly.
    """
    forward_pe_value = coerce_finite_float(forward_pe)
    if price is None or forward_pe_value is None or forward_pe_value == 0:
        return "N/A"
    return f"{(price / forward_pe_value):.2f}"


__all__ = [
    "calculate_change_percent",
    "coerce_finite_float",
    "derive_forward_eps",
    "format_analyst_count",
    "format_fractional_percent",
    "format_growth_percentage",
    "format_large_number",
    "format_percent_ratio",
    "format_price",
    "format_ratio",
    "format_short_ratio",
    "map_recommendation",
]
