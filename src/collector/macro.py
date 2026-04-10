"""Collect macro context: VIX level, upcoming FOMC/CPI/employment dates."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from src.utils.network import can_open_tcp_connection

logger = logging.getLogger(__name__)

# Static economic calendar — updated periodically.
# Source: Federal Reserve, BLS published schedules.
_FOMC_DATES_2026 = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]
_CPI_DATES_2026 = [
    "2026-01-14", "2026-02-11", "2026-03-11", "2026-04-14",
    "2026-05-13", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-15", "2026-10-13", "2026-11-12", "2026-12-09",
]
_EMPLOYMENT_DATES_2026 = [
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
    "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
    "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
]


def collect_macro_context(
    run_date: date,
    *,
    vix_data: dict[str, Any] | None = None,
    lookahead_days: int = 14,
) -> dict[str, Any]:
    """Return macro context dict for the given date.

    Parameters
    ----------
    run_date : date
        Pipeline execution date.
    vix_data : dict | None
        Pre-collected VIX data from market overview (price, change_percent).
    lookahead_days : int
        Days ahead to scan for upcoming macro events.
    """
    context: dict[str, Any] = {}

    # VIX level
    if vix_data:
        context["vix"] = {
            "level": vix_data.get("price", "N/A"),
            "change": vix_data.get("change_percent", "N/A"),
            "regime": _classify_vix_regime(vix_data.get("price")),
        }
    else:
        context["vix"] = {"level": "N/A", "change": "N/A", "regime": "N/A"}

    # Upcoming macro events
    context["upcoming_macro_events"] = _find_upcoming_events(run_date, lookahead_days)
    context.update(_collect_macro_market_series())

    return context


def _classify_vix_regime(vix_level: Any) -> str:
    if vix_level is None or vix_level == "N/A":
        return "N/A"
    try:
        level = float(str(vix_level).replace(",", ""))
    except (ValueError, TypeError):
        return "N/A"

    if level < 15:
        return "저변동성 (complacent)"
    if level < 20:
        return "정상 범위"
    if level < 30:
        return "경계 (elevated)"
    return "공포 (fear)"


def _find_upcoming_events(run_date: date, lookahead_days: int) -> list[dict[str, str]]:
    cutoff = run_date + timedelta(days=lookahead_days)
    events: list[dict[str, str]] = []

    for date_str in _FOMC_DATES_2026:
        event_date = _safe_parse_date(date_str)
        if event_date and run_date <= event_date <= cutoff:
            days_until = (event_date - run_date).days
            events.append({
                "type": "FOMC",
                "date": date_str,
                "days_until": str(days_until),
                "label": "FOMC 금리 결정",
                "impact": "high",
            })

    for date_str in _CPI_DATES_2026:
        event_date = _safe_parse_date(date_str)
        if event_date and run_date <= event_date <= cutoff:
            days_until = (event_date - run_date).days
            events.append({
                "type": "CPI",
                "date": date_str,
                "days_until": str(days_until),
                "label": "CPI 물가지표 발표",
                "impact": "high",
            })

    for date_str in _EMPLOYMENT_DATES_2026:
        event_date = _safe_parse_date(date_str)
        if event_date and run_date <= event_date <= cutoff:
            days_until = (event_date - run_date).days
            events.append({
                "type": "Employment",
                "date": date_str,
                "days_until": str(days_until),
                "label": "고용지표 (Non-Farm Payrolls)",
                "impact": "high",
            })

    events.sort(key=lambda e: e.get("date", ""))
    return events


def _safe_parse_date(date_str: str) -> date | None:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


def _collect_macro_market_series() -> dict[str, dict[str, str]]:
    if not can_open_tcp_connection("query1.finance.yahoo.com", 443):
        return {}

    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return {}

    symbol_map = {
        "us10y": ("^TNX", "미국 10년물"),
        "dxy": ("DX-Y.NYB", "달러 인덱스"),
        "copper": ("HG=F", "구리 선물"),
    }
    result: dict[str, dict[str, str]] = {}
    for key, (symbol, label) in symbol_map.items():
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", interval="1d")
            if history is None or history.empty:
                continue
            close_series = history["Close"].dropna()
            if close_series.empty:
                continue
            latest = float(close_series.iloc[-1])
            previous = float(close_series.iloc[-2]) if len(close_series) > 1 else latest
            change_pct = ((latest - previous) / previous * 100) if previous else 0.0
            result[key] = {
                "label": label,
                "price": f"{latest:,.2f}",
                "change": f"{change_pct:+.2f}%",
            }
        except Exception:
            continue
    return result
