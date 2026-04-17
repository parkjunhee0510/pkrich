"""Finnhub free tier collector.

Provides analyst recommendation trends, earnings calendar data, peer lookup,
and lightweight economic calendar events.
Free tier allows 60 API calls/minute — more than enough for this batch flow.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from typing import Any
from urllib import request
from urllib.error import HTTPError

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


def collect_finnhub_economic_calendar(
    run_date: date,
    *,
    lookahead_days: int = 14,
) -> list[dict[str, str]]:
    """Fetch a narrow set of US macro events for the near-term calendar.

    Finnhub returns a broader economic calendar, so we normalize only the
    events this project already surfaces: FOMC, CPI, and US employment/NFP.
    """
    try:
        data = _fetch_json(
            "calendar/economic",
            {
                "from": run_date.isoformat(),
                "to": (run_date + timedelta(days=lookahead_days)).isoformat(),
            },
        )
    except HTTPError as exc:
        if exc.code == 403:
            record_pipeline_event(
                "collector",
                "info",
                "finnhub_economic_calendar_unavailable",
                reason="http_403",
            )
            return []
        record_pipeline_event(
            "collector",
            "warning",
            "finnhub_economic_calendar_failed",
            error=str(exc),
        )
        return []
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "finnhub_economic_calendar_failed",
            error=str(exc),
        )
        return []

    raw_events: Any = []
    if isinstance(data, list):
        raw_events = data
    elif isinstance(data, dict):
        raw_events = (
            data.get("economicCalendar")
            or data.get("economicCalendarData")
            or data.get("events")
            or []
        )

    if not isinstance(raw_events, list):
        return []

    normalized: list[dict[str, str]] = []
    for entry in raw_events:
        normalized_entry = _normalize_macro_event(entry, run_date)
        if normalized_entry:
            normalized.append(normalized_entry)

    normalized.sort(key=lambda item: (item.get("date", ""), item.get("type", "")))
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in normalized:
        key = (entry.get("type", ""), entry.get("date", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    if deduped:
        record_pipeline_event(
            "collector",
            "info",
            "finnhub_economic_calendar",
            event_count=len(deduped),
        )
    return deduped


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


def _normalize_macro_event(entry: Any, run_date: date) -> dict[str, str] | None:
    if not isinstance(entry, dict):
        return None

    title = " ".join(
        str(entry.get(key, "")).strip()
        for key in ("event", "indicator", "release", "title")
        if str(entry.get(key, "")).strip()
    ).strip()
    if not title:
        return None

    normalized_title = title.lower()
    event_meta = _match_macro_event_metadata(normalized_title)
    if event_meta is None:
        return None

    date_value = (
        str(entry.get("date") or entry.get("time") or entry.get("releaseDate") or "")
        .strip()
        .replace("Z", "")
    )
    if not date_value:
        return None
    event_date = _parse_event_date(date_value)
    if event_date is None:
        return None

    days_until = (event_date - run_date).days
    if days_until < 0:
        return None

    event_code = str(event_meta["event_code"])
    actual = _extract_macro_numeric(entry, "actual", "actualValue", "actualRelease")
    consensus = _extract_macro_numeric(entry, "consensus", "estimate", "forecast")
    previous = _extract_macro_numeric(entry, "previous", "prior", "previousValue")

    return {
        "type": event_code,
        "event_code": event_code,
        "category": str(event_meta["category"]),
        "date": event_date.isoformat(),
        "days_until": str(days_until),
        "label": str(event_meta["label"]),
        "impact": str(event_meta["impact"]),
        "source": "finnhub",
        "actual": actual,
        "consensus": consensus,
        "previous": previous,
        "surprise_direction": _infer_surprise_direction(event_code, actual, consensus),
        "market_bias": str(event_meta["market_bias"]),
        "description": str(event_meta["description"]),
        "sensitivity_tags": ",".join(event_meta.get("sensitivity_tags", [])),
    }


def _match_macro_event_metadata(normalized_title: str) -> dict[str, object] | None:
    if "fomc" in normalized_title or "federal reserve" in normalized_title or "interest rate" in normalized_title:
        return {
            "event_code": "FOMC",
            "category": "rates",
            "label": "FOMC Rate Decision",
            "impact": "high",
            "market_bias": "A hawkish decision can pressure long-duration growth assets.",
            "description": "The Fed rate path and dot plot directly affect rate-sensitive assets.",
            "sensitivity_tags": ["long_duration_growth", "financials", "dividend"],
        }
    if "cpi" in normalized_title or "consumer price index" in normalized_title:
        return {
            "event_code": "CPI",
            "category": "inflation",
            "label": "CPI Consumer Inflation",
            "impact": "high",
            "market_bias": "A hotter CPI can lift rate expectations and weigh on growth multiples.",
            "description": "Consumer inflation shapes rate expectations and equity valuation.",
            "sensitivity_tags": ["long_duration_growth", "consumer", "energy", "industrials"],
        }
    if "ppi" in normalized_title or "producer price index" in normalized_title:
        return {
            "event_code": "PPI",
            "category": "inflation",
            "label": "PPI Producer Inflation",
            "impact": "high",
            "market_bias": "Higher producer inflation can pressure margins and foreshadow CPI risk.",
            "description": "Producer prices give an early read on cost pressure and margin risk.",
            "sensitivity_tags": ["industrials", "energy", "materials", "consumer"],
        }
    if "unemployment rate" in normalized_title:
        return {
            "event_code": "UNRATE",
            "category": "labor",
            "label": "Unemployment Rate",
            "impact": "high",
            "market_bias": "A rising or falling unemployment rate quickly shifts growth expectations.",
            "description": "The unemployment rate signals labor cooling or overheating.",
            "sensitivity_tags": ["industrials", "energy", "consumer", "financials"],
        }
    if "nonfarm payroll" in normalized_title or "non-farm payroll" in normalized_title or "payroll" in normalized_title:
        return {
            "event_code": "NFP",
            "category": "labor",
            "label": "NFP Payrolls",
            "impact": "high",
            "market_bias": "A strong payroll print can boost growth expectations but revive rate fears.",
            "description": "Payroll growth is a key read on labor strength, growth, and rate sensitivity.",
            "sensitivity_tags": ["industrials", "energy", "consumer", "long_duration_growth"],
        }
    if "retail sales" in normalized_title or "advance retail sales" in normalized_title:
        return {
            "event_code": "RETAIL_SALES",
            "category": "consumer",
            "label": "Retail Sales",
            "impact": "high",
            "market_bias": "Strong consumer spending can help cyclicals while reviving rate repricing.",
            "description": "Retail sales measure the strength of US consumer demand.",
            "sensitivity_tags": ["consumer", "communication", "industrials"],
        }
    if (
        "employment" in normalized_title
        or "jobless" in normalized_title
        or "unemployment" in normalized_title
    ):
        return {
            "event_code": "NFP",
            "category": "labor",
            "label": "NFP Payrolls",
            "impact": "high",
            "market_bias": "A strong payroll print can boost growth expectations but revive rate fears.",
            "description": "Hotter or cooler-than-expected data can quickly reprice macro-sensitive assets.",
            "sensitivity_tags": ["industrials", "energy", "consumer", "long_duration_growth"],
        }
    return None


def _extract_macro_numeric(entry: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = entry.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text:
            return text
    return "N/A"


def _infer_surprise_direction(event_code: str, actual: str, consensus: str) -> str:
    try:
        actual_value = float(actual.replace("%", "").replace(",", ""))
        consensus_value = float(consensus.replace("%", "").replace(",", ""))
    except (AttributeError, TypeError, ValueError):
        return "N/A"

    if actual_value == consensus_value:
        return "N/A"
    stronger = actual_value > consensus_value
    if event_code in {"CPI", "PPI"}:
        return "hotter" if stronger else "cooler"
    if event_code in {"NFP", "RETAIL_SALES"}:
        return "stronger" if stronger else "weaker"
    if event_code == "UNRATE":
        return "weaker" if stronger else "stronger"
    return "N/A"


def _parse_event_date(raw_value: str) -> date | None:
    trimmed = raw_value.strip()
    if not trimmed:
        return None
    for candidate in (trimmed[:10], trimmed):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    return None
