"""YFinance extraction helpers extracted from `src/collector/price.py`.

These functions were originally private helpers on the legacy god-module
(`price.py`). Moving them here:
  * Keeps yfinance-specific extraction logic separate from the main pipeline.
  * Allows both `price.py` and `yfinance_provider.py` to import from this
    module without circular dependency (this module never imports price.py
    at module level).
  * Provides a clear migration path as price.py shrinks toward deletion.

Note on circular imports: `_extract_yfinance_events` internally calls
helpers that still live in `price.py`. Those are imported lazily (inside
the function body) so that importing *this* module at module level in
`price.py` does not create a circular import.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from src.collector.helpers.formatters import (
    calculate_change_percent as _calculate_change_percent,
    coerce_finite_float as _coerce_finite_float,
    format_large_number as _format_large_number,
    format_ratio as _format_ratio,
)


# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------

def _configure_yfinance_cache(yf: Any) -> None:
    cache_dir = Path(".cache") / "yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir.resolve()))
    except Exception:
        return


# ---------------------------------------------------------------------------
# Price snapshot helpers
# ---------------------------------------------------------------------------

def _select_price_snapshot(history: object, info: dict[str, Any]) -> tuple[float | None, float | None]:
    from src.collector.technicals import _extract_history_values

    close_values = _extract_history_values(history, "Close")
    latest_history_close = close_values[-1] if close_values else None
    valid_closes = [value for value in close_values if value is not None]
    live_price = _coerce_finite_float(info.get("regularMarketPrice"))
    if live_price is None:
        live_price = _coerce_finite_float(info.get("currentPrice"))
    previous_close = _coerce_finite_float(info.get("previousClose"))

    if latest_history_close is not None:
        baseline = valid_closes[-2] if len(valid_closes) > 1 else previous_close
        return latest_history_close, _calculate_change_percent(latest_history_close, baseline)

    if live_price is not None:
        baseline = previous_close if previous_close is not None else (valid_closes[-1] if valid_closes else None)
        return live_price, _calculate_change_percent(live_price, baseline)

    if valid_closes:
        latest_valid_close = valid_closes[-1]
        baseline = valid_closes[-2] if len(valid_closes) > 1 else previous_close
        return latest_valid_close, _calculate_change_percent(latest_valid_close, baseline)

    return None, None


# ---------------------------------------------------------------------------
# OHLCV extraction helpers
# ---------------------------------------------------------------------------

def _extract_latest_ohlcv(
    history: object,
    price: float | None,
    open_price: float | None,
    volume_str: str,
) -> dict[str, str]:
    """Extract latest-day OHLCV from history DataFrame for candlestick charting."""
    result: dict[str, str] = {}
    try:
        import pandas as pd
        if isinstance(history, pd.DataFrame) and not history.empty:
            last_row = history.iloc[-1]
            result["open"] = f"{float(last_row.get('Open', 0)):.2f}" if last_row.get("Open") is not None else "N/A"
            result["high"] = f"{float(last_row.get('High', 0)):.2f}" if last_row.get("High") is not None else "N/A"
            result["low"] = f"{float(last_row.get('Low', 0)):.2f}" if last_row.get("Low") is not None else "N/A"
            result["close"] = f"{float(last_row.get('Close', 0)):.2f}" if last_row.get("Close") is not None else "N/A"
            vol = last_row.get("Volume")
            result["volume"] = str(int(vol)) if vol is not None and vol == vol else "N/A"
            return result
    except Exception:
        pass
    # fallback from info dict
    if open_price is not None:
        result["open"] = f"{open_price:.2f}"
    if price is not None:
        result["close"] = f"{price:.2f}"
    result["volume"] = volume_str
    return result


def _extract_historical_price_rows(
    history: object,
    ticker_symbol: str,
    currency: str,
) -> list[dict[str, str]]:
    """Normalize yfinance daily history into datastore-compatible backfill rows."""
    try:
        import pandas as pd

        if not isinstance(history, pd.DataFrame) or history.empty:
            return []
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    previous_close: float | None = None
    for idx_val, row in history.iterrows():
        try:
            row_date = idx_val.date() if hasattr(idx_val, "date") else date.fromisoformat(str(idx_val)[:10])
        except Exception:
            continue

        open_value = _coerce_finite_float(row.get("Open"))
        high_value = _coerce_finite_float(row.get("High"))
        low_value = _coerce_finite_float(row.get("Low"))
        close_value = _coerce_finite_float(row.get("Close"))
        volume_value = _coerce_finite_float(row.get("Volume"))
        if close_value is None:
            continue

        daily_change = _calculate_change_percent(close_value, previous_close)
        rows.append(
            {
                "date": row_date.isoformat(),
                "ticker": ticker_symbol,
                "price": f"{close_value:.2f} {currency}",
                "daily_change": f"{daily_change:+.2f}%" if daily_change is not None else "N/A",
                "market_cap": "N/A",
                "trailing_pe": "N/A",
                "eps": "N/A",
                "52w_high": "N/A",
                "52w_low": "N/A",
                "open": f"{open_value:.2f}" if open_value is not None else "N/A",
                "high": f"{high_value:.2f}" if high_value is not None else "N/A",
                "low": f"{low_value:.2f}" if low_value is not None else "N/A",
                "close": f"{close_value:.2f}",
                "volume": _format_large_number(volume_value),
            }
        )
        previous_close = close_value
    return rows


# ---------------------------------------------------------------------------
# Quarterly financials
# ---------------------------------------------------------------------------

def _extract_yfinance_quarterly_financials(ticker: Any) -> list[dict[str, str]]:
    # Import lazily to avoid circular dependency with price.py
    from src.collector.price import (  # noqa: PLC0415
        _coerce_event_date,
        _format_quarter,
        _extract_yfinance_earnings_history,
        _lookup_quarterly_enrichment,
        _statement_value,
    )

    statement = getattr(ticker, "quarterly_income_stmt", None)
    if statement is None or getattr(statement, "empty", False):
        return []

    try:
        columns = list(statement.columns)[:8]
    except Exception:
        return []

    earnings_history = _extract_yfinance_earnings_history(ticker)
    reports: list[dict[str, str]] = []
    for column in columns:
        fiscal_date = _coerce_event_date(column).isoformat() if _coerce_event_date(column) else ""
        quarter = _format_quarter(column)
        earnings_entry = _lookup_quarterly_enrichment(earnings_history, fiscal_date, quarter)
        statement_eps = _format_ratio(_statement_value(statement, ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"], column))
        reports.append(
            {
                "fiscal_date": fiscal_date,
                "quarter": quarter,
                "revenue": _format_large_number(_statement_value(statement, ["Total Revenue", "Operating Revenue", "TotalRevenue"], column)),
                "operating_income": _format_large_number(_statement_value(statement, ["Operating Income", "OperatingIncome"], column)),
                "eps": statement_eps if statement_eps != "N/A" else str(earnings_entry.get("actual_eps", "N/A")),
                "estimated_eps": str(earnings_entry.get("estimated_eps", "N/A")),
                "surprise_pct": str(earnings_entry.get("surprise_pct", "N/A")),
                "beat_miss": str(earnings_entry.get("beat_miss", "N/A")),
            }
        )
    return reports


# ---------------------------------------------------------------------------
# Events extraction
# ---------------------------------------------------------------------------

def _extract_yfinance_events(
    ticker_symbol: str,
    info: dict[str, Any],
    ticker: Any,
    run_date: date,
) -> list[dict[str, str]]:
    # Import lazily to avoid circular dependency with price.py
    from src.collector.price import (  # noqa: PLC0415
        _extract_yfinance_earnings_timing,
        _extract_calendar_events,
        _normalize_upcoming_events,
    )

    earnings_timing = _extract_yfinance_earnings_timing(info)
    raw_events = [
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsDate"), "timing": earnings_timing},
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsTimestamp"), "timing": earnings_timing},
        {"type": "earnings", "label": "실적 발표", "date": info.get("earningsTimestampStart"), "timing": earnings_timing},
        {"type": "ex_dividend", "label": "배당락일", "date": info.get("exDividendDate")},
        {"type": "dividend", "label": "배당 지급일", "date": info.get("dividendDate")},
    ]

    calendar = getattr(ticker, "calendar", None)
    raw_events.extend(_extract_calendar_events(calendar))
    return _normalize_upcoming_events(
        raw_events,
        run_date,
        ticker=ticker_symbol,
        source="yfinance",
        calendar_shape=type(calendar).__name__ if calendar is not None else "",
    )


__all__ = [
    "_configure_yfinance_cache",
    "_select_price_snapshot",
    "_extract_latest_ohlcv",
    "_extract_historical_price_rows",
    "_extract_yfinance_quarterly_financials",
    "_extract_yfinance_events",
]
