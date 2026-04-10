"""Polygon.io options flow collector.

Provides aggregated options data including unusual activity detection
and historical IV data. Requires Polygon.io Starter plan ($9/month).
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from typing import Any
from urllib import request

from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_POLYGON_BASE = "https://api.polygon.io"
_REQUEST_DELAY = 12.0  # Polygon Starter: 5 calls/min (12s between calls)
_LAST_REQUEST_AT: float = 0.0


def _get_api_key() -> str | None:
    return os.getenv("POLYGON_API_KEY") or None


def _throttle() -> None:
    global _LAST_REQUEST_AT  # noqa: PLW0603
    now = time.monotonic()
    elapsed = now - _LAST_REQUEST_AT
    if elapsed < _REQUEST_DELAY:
        time.sleep(_REQUEST_DELAY - elapsed)
    _LAST_REQUEST_AT = time.monotonic()


def _fetch_json(path: str, params: dict[str, str] | None = None) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None
    query_parts = [f"apiKey={api_key}"]
    if params:
        query_parts.extend(f"{k}={v}" for k, v in params.items())
    url = f"{_POLYGON_BASE}{path}?{'&'.join(query_parts)}"
    _throttle()
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_polygon_ready() -> bool:
    """Check if Polygon API key is set and host is reachable."""
    if not _get_api_key():
        return False
    return can_open_tcp_connection("api.polygon.io", 443)


def collect_options_flow(ticker: str, run_date: date) -> dict[str, str]:
    """Collect aggregated options flow data from Polygon.io.

    Returns dict with keys: net_call_volume, net_put_volume,
    put_call_volume_ratio, unusual_activity, iv_rank_note.
    """
    try:
        # Get options snapshot for the ticker
        data = _fetch_json(f"/v3/snapshot/options/{ticker}", {
            "limit": "50",
            "order": "desc",
            "sort": "volume",
        })

        if not data or not isinstance(data, dict):
            return {}

        results_list = data.get("results", [])
        if not results_list:
            return {}

        total_call_volume = 0
        total_put_volume = 0
        total_call_oi = 0
        total_put_oi = 0
        iv_values: list[float] = []
        unusual_strikes: list[str] = []

        for option in results_list:
            if not isinstance(option, dict):
                continue

            details = option.get("details", {})
            day_data = option.get("day", {})
            greeks = option.get("greeks", {})

            contract_type = str(details.get("contract_type", "")).lower()
            volume = _safe_float(day_data.get("volume")) or 0
            open_interest = _safe_float(option.get("open_interest")) or 0
            iv = _safe_float(option.get("implied_volatility"))
            strike = _safe_float(details.get("strike_price"))

            if contract_type == "call":
                total_call_volume += volume
                total_call_oi += open_interest
            elif contract_type == "put":
                total_put_volume += volume
                total_put_oi += open_interest

            if iv is not None:
                iv_values.append(iv)

            # Detect unusual activity (volume > 5x open interest)
            if volume > 0 and open_interest > 0 and volume > open_interest * 5:
                strike_label = f"${strike:.0f}" if strike else "?"
                unusual_strikes.append(f"{contract_type.upper()} {strike_label} vol={int(volume)}")

        result: dict[str, str] = {}

        if total_call_volume > 0 or total_put_volume > 0:
            result["net_call_volume"] = f"{int(total_call_volume):,}"
            result["net_put_volume"] = f"{int(total_put_volume):,}"

            total_vol = total_call_volume + total_put_volume
            if total_vol > 0:
                pc_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 999
                result["put_call_volume_ratio"] = f"{pc_ratio:.2f}"

                # Sentiment label
                if pc_ratio > 1.5:
                    result["flow_sentiment"] = "bearish"
                elif pc_ratio < 0.5:
                    result["flow_sentiment"] = "bullish"
                else:
                    result["flow_sentiment"] = "neutral"

        if unusual_strikes:
            result["unusual_activity"] = "; ".join(unusual_strikes[:3])

        if iv_values:
            avg_iv = sum(iv_values) / len(iv_values)
            result["avg_iv"] = f"{avg_iv * 100:.1f}%"

        if result:
            record_pipeline_event(
                "collector", "info", "polygon_options_flow",
                ticker=ticker, fields=len(result),
            )
        return result

    except Exception as exc:
        record_pipeline_event(
            "collector", "warning", "polygon_options_flow_failed",
            ticker=ticker, error=str(exc),
        )
        return {}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        return None if f != f else f  # NaN check
    except (TypeError, ValueError):
        return None
