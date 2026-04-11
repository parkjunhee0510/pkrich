"""Finnhub free tier collector.

Provides analyst recommendation trends and earnings calendar data.
Free tier allows 60 API calls/minute — more than enough.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from typing import Any
from urllib import request

from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_REQUEST_DELAY = 0.2  # 60 calls/min limit → 1 per second safe, but 0.2s is fine
_LAST_REQUEST_AT: float = 0.0


def _get_api_key() -> str | None:
    return os.getenv("FINNHUB_API_KEY") or None


def _throttle() -> None:
    global _LAST_REQUEST_AT  # noqa: PLW0603
    now = time.monotonic()
    elapsed = now - _LAST_REQUEST_AT
    if elapsed < _REQUEST_DELAY:
        time.sleep(_REQUEST_DELAY - elapsed)
    _LAST_REQUEST_AT = time.monotonic()


def _fetch_json(endpoint: str, params: dict[str, str] | None = None) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None
    query_parts = [f"token={api_key}"]
    if params:
        query_parts.extend(f"{k}={v}" for k, v in params.items())
    url = f"{_FINNHUB_BASE}/{endpoint}?{'&'.join(query_parts)}"
    _throttle()
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_finnhub_ready() -> bool:
    """Check if Finnhub API key is set and host is reachable."""
    if not _get_api_key():
        return False
    return can_open_tcp_connection("finnhub.io", 443)


def collect_finnhub_recommendations(ticker: str) -> list[dict[str, str]]:
    """Fetch analyst recommendation trends (upgrade/downgrade/maintain history)."""
    try:
        data = _fetch_json("stock/recommendation", {"symbol": ticker})
        if not data or not isinstance(data, list):
            return []

        results: list[dict[str, str]] = []
        for entry in data[:6]:  # Last 6 periods
            if not isinstance(entry, dict):
                continue
            period = str(entry.get("period", ""))
            strong_buy = int(entry.get("strongBuy", 0))
            buy = int(entry.get("buy", 0))
            hold = int(entry.get("hold", 0))
            sell = int(entry.get("sell", 0))
            strong_sell = int(entry.get("strongSell", 0))

            total = strong_buy + buy + hold + sell + strong_sell
            if total == 0:
                continue

            bullish = strong_buy + buy
            bearish = sell + strong_sell
            consensus = "Buy" if bullish > hold + bearish else ("Sell" if bearish > hold + bullish else "Hold")

            results.append({
                "period": period,
                "strong_buy": str(strong_buy),
                "buy": str(buy),
                "hold": str(hold),
                "sell": str(sell),
                "strong_sell": str(strong_sell),
                "total": str(total),
                "consensus": consensus,
            })

        # Detect trend shift (latest vs 3 months ago)
        if len(results) >= 2:
            latest_bull = int(results[0].get("strong_buy", "0")) + int(results[0].get("buy", "0"))
            prev_bull = int(results[1].get("strong_buy", "0")) + int(results[1].get("buy", "0"))
            if latest_bull > prev_bull:
                results[0]["trend"] = "upgrading"
            elif latest_bull < prev_bull:
                results[0]["trend"] = "downgrading"
            else:
                results[0]["trend"] = "stable"

        if results:
            record_pipeline_event(
                "collector", "info", "finnhub_recommendations",
                ticker=ticker, periods=len(results),
            )
        return results

    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "finnhub_recommendations_failed",
            ticker=ticker, error=str(exc),
        )
        return []


def collect_finnhub_earnings_calendar(ticker: str, run_date: date) -> list[dict[str, str]]:
    """Fetch upcoming and recent earnings dates with consensus estimates."""
    try:
        from_date = (run_date - timedelta(days=30)).isoformat()
        to_date = (run_date + timedelta(days=90)).isoformat()

        data = _fetch_json("calendar/earnings", {
            "symbol": ticker,
            "from": from_date,
            "to": to_date,
        })

        if not data or not isinstance(data, dict):
            return []

        earnings_list = data.get("earningsCalendar", [])
        if not earnings_list:
            return []

        results: list[dict[str, str]] = []
        for entry in earnings_list[:4]:
            if not isinstance(entry, dict):
                continue

            earnings_date = str(entry.get("date", ""))
            eps_actual = entry.get("epsActual")
            eps_estimate = entry.get("epsEstimate")
            revenue_actual = entry.get("revenueActual")
            revenue_estimate = entry.get("revenueEstimate")
            hour = str(entry.get("hour", ""))  # bmo, amc, dmh

            row: dict[str, str] = {
                "date": earnings_date,
                "timing": _map_timing(hour),
            }
            if eps_estimate is not None:
                row["eps_estimate"] = f"{float(eps_estimate):.2f}"
            if eps_actual is not None:
                row["eps_actual"] = f"{float(eps_actual):.2f}"
            if revenue_estimate is not None:
                row["revenue_estimate"] = _format_large(float(revenue_estimate))
            if revenue_actual is not None:
                row["revenue_actual"] = _format_large(float(revenue_actual))

            results.append(row)

        return results

    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "finnhub_earnings_calendar_failed",
            ticker=ticker, error=str(exc),
        )
        return []


def collect_finnhub_peers(ticker: str) -> list[str]:
    """Fetch peer companies for a ticker (up to 5)."""
    try:
        data = _fetch_json("stock/peers", {"symbol": ticker})
        if not data or not isinstance(data, list):
            return []
        # Finnhub returns the ticker itself as the first element
        peers = [p for p in data if isinstance(p, str) and p != ticker][:5]
        if peers:
            record_pipeline_event(
                "collector", "info", "finnhub_peers",
                ticker=ticker, count=len(peers),
            )
        return peers
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "finnhub_peers_failed",
            ticker=ticker, error=str(exc),
        )
        return []


def _map_timing(hour: str) -> str:
    h = hour.lower().strip()
    if h == "bmo":
        return "BMO"
    if h == "amc":
        return "AMC"
    if h == "dmh":
        return "During Market Hours"
    return ""


def _format_large(value: float) -> str:
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value / 1e12:.1f}T"
    if abs_val >= 1e9:
        return f"${value / 1e9:.1f}B"
    if abs_val >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"
