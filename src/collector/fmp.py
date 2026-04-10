"""Financial Modeling Prep (FMP) API collector.

Provides analyst estimate revisions, insider trading, institutional
holder changes, and earnings surprises data.

Requires ``FMP_API_KEY`` environment variable. Starter plan ($19/month)
allows 250 calls/day — more than enough for 8 tickers × 4 endpoints × 5 days.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from typing import Any
from urllib import request
from urllib.error import URLError

from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_FMP_BASE = "https://financialmodelingprep.com/api/v3"
_FMP_DELAY_SECONDS = 0.5
_FMP_LAST_CALL_AT: float = 0.0


def _get_api_key() -> str | None:
    return os.getenv("FMP_API_KEY") or None


def _throttle() -> None:
    global _FMP_LAST_CALL_AT  # noqa: PLW0603
    now = time.monotonic()
    elapsed = now - _FMP_LAST_CALL_AT
    if elapsed < _FMP_DELAY_SECONDS:
        time.sleep(_FMP_DELAY_SECONDS - elapsed)
    _FMP_LAST_CALL_AT = time.monotonic()


def _fetch_json(endpoint: str, params: dict[str, str] | None = None) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None
    query_parts = [f"apikey={api_key}"]
    if params:
        query_parts.extend(f"{k}={v}" for k, v in params.items())
    url = f"{_FMP_BASE}/{endpoint}?{'&'.join(query_parts)}"
    _throttle()
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_fmp_ready() -> bool:
    """Check if FMP API key is set and host is reachable."""
    if not _get_api_key():
        return False
    return can_open_tcp_connection("financialmodelingprep.com", 443)


# ── Analyst Estimate Revisions ──────────────────────────────────────

def collect_fmp_analyst_estimates(ticker: str, run_date: date) -> dict[str, str]:
    """Fetch analyst estimates and compute revision trends.

    Returns dict with keys: current_eps, 30d_ago_eps, 90d_ago_eps,
    current_revenue, revision_pct, direction.
    """
    try:
        data = _fetch_json(f"analyst-estimates/{ticker}", {"limit": "8"})
        if not data or not isinstance(data, list):
            return {}

        # FMP returns estimates sorted newest first (annual/quarterly)
        estimates = [e for e in data if isinstance(e, dict)]
        if not estimates:
            return {}

        current = estimates[0]
        result: dict[str, str] = {}

        current_eps = _safe_float(current.get("estimatedEpsAvg"))
        if current_eps is not None:
            result["current_eps"] = f"{current_eps:.2f}"

        current_rev = _safe_float(current.get("estimatedRevenueAvg"))
        if current_rev is not None:
            result["current_revenue"] = _format_large(current_rev)

        # Find estimates from ~30 and ~90 days ago for revision comparison
        for entry in estimates[1:]:
            entry_date = entry.get("date", "")
            if not entry_date:
                continue
            try:
                ed = date.fromisoformat(entry_date)
            except (ValueError, TypeError):
                continue
            days_diff = (run_date - ed).days
            eps_val = _safe_float(entry.get("estimatedEpsAvg"))
            if eps_val is None:
                continue

            if 20 <= days_diff <= 45 and "30d_ago_eps" not in result:
                result["30d_ago_eps"] = f"{eps_val:.2f}"
            elif 75 <= days_diff <= 120 and "90d_ago_eps" not in result:
                result["90d_ago_eps"] = f"{eps_val:.2f}"

        # Compute revision direction
        if current_eps is not None:
            compare_eps = _safe_float(result.get("30d_ago_eps")) or _safe_float(result.get("90d_ago_eps"))
            if compare_eps is not None and compare_eps != 0:
                pct = ((current_eps - compare_eps) / abs(compare_eps)) * 100
                result["revision_pct"] = f"{pct:+.1f}%"
                if pct > 1:
                    result["direction"] = "up"
                elif pct < -1:
                    result["direction"] = "down"
                else:
                    result["direction"] = "stable"

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_analyst_estimates",
                ticker=ticker, fields=len(result),
            )
        return result
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_analyst_estimates_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


# ── Insider Trading ─────────────────────────────────────────────────

def collect_fmp_insider_trading(ticker: str, run_date: date) -> list[dict[str, str]]:
    """Fetch recent insider transactions (last 90 days)."""
    try:
        data = _fetch_json("insider-trading", {"symbol": ticker, "limit": "20"})
        if not data or not isinstance(data, list):
            return []

        cutoff = run_date - timedelta(days=90)
        results: list[dict[str, str]] = []

        for tx in data:
            if not isinstance(tx, dict):
                continue
            tx_date_str = tx.get("transactionDate", "")
            try:
                tx_date = date.fromisoformat(tx_date_str)
            except (ValueError, TypeError):
                continue
            if tx_date < cutoff:
                continue

            shares = _safe_float(tx.get("securitiesTransacted"))
            price = _safe_float(tx.get("price"))
            value = shares * price if shares and price else None

            results.append({
                "name": str(tx.get("reportingName", "Unknown")),
                "title": str(tx.get("typeOfOwner", "")),
                "type": _classify_transaction(tx.get("acquistionOrDisposition", ""), tx.get("transactionType", "")),
                "shares": f"{int(shares):,}" if shares else "N/A",
                "value": _format_money(value),
                "date": tx_date_str,
            })

        if results:
            record_pipeline_event(
                "collector", "info", "fmp_insider_trading",
                ticker=ticker, count=len(results),
            )
        return results[:10]
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_insider_trading_failed",
            ticker=ticker, error=str(exc),
        )
        return []


# ── Institutional Holders ───────────────────────────────────────────

def collect_fmp_institutional_holders(ticker: str) -> dict[str, str]:
    """Fetch top institutional holders and compute net flow."""
    try:
        data = _fetch_json(f"institutional-holder/{ticker}")
        if not data or not isinstance(data, list):
            return {}

        holders = [h for h in data if isinstance(h, dict)][:10]
        if not holders:
            return {}

        total_shares = sum(_safe_float(h.get("shares")) or 0 for h in holders)
        total_change = sum(_safe_float(h.get("change")) or 0 for h in holders)

        # Find biggest buyer and seller
        buyers = sorted(
            [h for h in holders if (_safe_float(h.get("change")) or 0) > 0],
            key=lambda h: _safe_float(h.get("change")) or 0,
            reverse=True,
        )
        sellers = sorted(
            [h for h in holders if (_safe_float(h.get("change")) or 0) < 0],
            key=lambda h: _safe_float(h.get("change")) or 0,
        )

        result: dict[str, str] = {
            "total_institutional_shares": _format_large(total_shares),
            "net_change": _format_shares_change(total_change),
        }

        if buyers:
            b = buyers[0]
            change = _safe_float(b.get("change")) or 0
            result["top_buyer"] = f"{b.get('holder', 'Unknown')} {_format_shares_change(change)}"

        if sellers:
            s = sellers[0]
            change = _safe_float(s.get("change")) or 0
            result["top_seller"] = f"{s.get('holder', 'Unknown')} {_format_shares_change(change)}"

        if result:
            record_pipeline_event(
                "collector", "info", "fmp_institutional_holders",
                ticker=ticker, holders=len(holders),
            )
        return result
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_institutional_holders_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


# ── Earnings Surprises ──────────────────────────────────────────────

def collect_fmp_earnings_surprises(ticker: str) -> list[dict[str, str]]:
    """Fetch historical earnings surprises (actual vs estimated)."""
    try:
        data = _fetch_json(f"earnings-surprises/{ticker}")
        if not data or not isinstance(data, list):
            return []

        results: list[dict[str, str]] = []
        for entry in data[:8]:
            if not isinstance(entry, dict):
                continue
            actual = _safe_float(entry.get("actualEarningResult"))
            estimated = _safe_float(entry.get("estimatedEarning"))

            row: dict[str, str] = {
                "date": str(entry.get("date", "")),
            }
            if actual is not None:
                row["actual"] = f"{actual:.2f}"
            if estimated is not None:
                row["estimated"] = f"{estimated:.2f}"
            if actual is not None and estimated is not None and estimated != 0:
                surprise = ((actual - estimated) / abs(estimated)) * 100
                row["surprise_pct"] = f"{surprise:+.1f}%"
                row["beat_miss"] = "beat" if surprise > 0 else ("miss" if surprise < 0 else "in-line")

            results.append(row)

        if results:
            record_pipeline_event(
                "collector", "info", "fmp_earnings_surprises",
                ticker=ticker, count=len(results),
            )
        return results
    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "fmp_earnings_surprises_failed",
            ticker=ticker, error=str(exc),
        )
        return []


# ── FMP News ────────────────────────────────────────────────────────

def collect_fmp_news(ticker: str, limit: int = 5) -> list[dict[str, str]]:
    """Fetch company-specific news from FMP (included in Starter plan)."""
    try:
        data = _fetch_json("stock_news", {"tickers": ticker, "limit": str(limit)})
        if not data or not isinstance(data, list):
            return []

        results: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append({
                "title": str(item.get("title", "")),
                "source": str(item.get("site", "")),
                "published_at": str(item.get("publishedDate", "")),
                "link": str(item.get("url", "")),
                "sentiment": str(item.get("sentiment", "")),
            })
        return results
    except Exception:
        return []


# ── Helpers ─────────────────────────────────────────────────────────

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None


def _format_large(value: float | None) -> str:
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value / 1e12:.1f}T"
    if abs_val >= 1e9:
        return f"${value / 1e9:.1f}B"
    if abs_val >= 1e6:
        return f"${value / 1e6:.1f}M"
    if abs_val >= 1e3:
        return f"${value / 1e3:.0f}K"
    return f"${value:.0f}"


def _format_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e6:
        return f"${value / 1e6:.1f}M"
    if abs_val >= 1e3:
        return f"${value / 1e3:.0f}K"
    return f"${value:,.0f}"


def _format_shares_change(value: float) -> str:
    if value >= 1e6:
        return f"+{value / 1e6:.1f}M shares"
    if value <= -1e6:
        return f"{value / 1e6:.1f}M shares"
    if value >= 1e3:
        return f"+{value / 1e3:.0f}K shares"
    if value <= -1e3:
        return f"{value / 1e3:.0f}K shares"
    return f"{value:+,.0f} shares"


def _classify_transaction(acq_disp: str, tx_type: str) -> str:
    acq_disp = (acq_disp or "").upper()
    tx_type = (tx_type or "").lower()
    if acq_disp == "A" or "purchase" in tx_type or "buy" in tx_type:
        return "buy"
    if acq_disp == "D" or "sale" in tx_type or "sell" in tx_type:
        return "sale"
    if "option" in tx_type or "exercise" in tx_type:
        return "option_exercise"
    return "other"
