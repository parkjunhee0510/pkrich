"""Polygon.io options flow collector.

Provides aggregated options data including unusual activity detection,
Max Pain, Implied Move, GEX, Greeks aggregates, IV Skew, OI
concentration, and enhanced unusual activity ranking.

Requires Polygon.io Starter plan ($9/month).
All Tier A metrics are derived from the single ``/v3/snapshot/options``
response — **zero additional API calls**.
"""

from __future__ import annotations

import json
import math
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


# ── Contract parsing ────────────────────────────────────────────────

def _parse_contracts(results_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize each option contract from the snapshot response."""
    contracts: list[dict[str, Any]] = []
    for option in results_list:
        if not isinstance(option, dict):
            continue
        details = option.get("details") or {}
        day_data = option.get("day") or {}
        greeks = option.get("greeks") or {}

        contract_type = str(details.get("contract_type", "")).lower()
        if contract_type not in ("call", "put"):
            continue

        strike = _safe_float(details.get("strike_price"))
        if strike is None or strike <= 0:
            continue

        expiry_str = str(details.get("expiration_date", ""))
        try:
            expiry = date.fromisoformat(expiry_str)
        except (ValueError, TypeError):
            expiry = None

        volume = _safe_float(day_data.get("volume")) or 0
        oi = _safe_float(option.get("open_interest")) or 0
        iv = _safe_float(option.get("implied_volatility"))

        close_price = _safe_float(day_data.get("close"))
        vwap = _safe_float(day_data.get("vwap"))
        mid_price = close_price or vwap

        contracts.append({
            "type": contract_type,
            "strike": strike,
            "volume": volume,
            "oi": oi,
            "iv": iv,
            "delta": _safe_float(greeks.get("delta")),
            "gamma": _safe_float(greeks.get("gamma")),
            "theta": _safe_float(greeks.get("theta")),
            "vega": _safe_float(greeks.get("vega")),
            "expiry": expiry,
            "dte": (expiry - date.today()).days if expiry else None,
            "mid_price": mid_price,
        })
    return contracts


def _extract_spot_price(data: dict[str, Any]) -> float | None:
    """Extract underlying asset price from the snapshot response."""
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    underlying = first.get("underlying_asset") or {}
    return _safe_float(underlying.get("price"))


# ── Tier A metric helpers (pure functions, never raise) ─────────────

def _compute_max_pain(contracts: list[dict[str, Any]], spot: float | None) -> dict[str, str] | None:
    """Compute the max pain strike (where total OI-weighted intrinsic value is minimized)."""
    strikes = sorted({c["strike"] for c in contracts})
    if len(strikes) < 3:
        return None

    best_strike = strikes[0]
    best_pain = float("inf")

    for k in strikes:
        pain = 0.0
        for c in contracts:
            if c["oi"] <= 0:
                continue
            if c["type"] == "call":
                pain += c["oi"] * max(k - c["strike"], 0)
            else:
                pain += c["oi"] * max(c["strike"] - k, 0)
        if pain < best_pain:
            best_pain = pain
            best_strike = k

    label = f"${best_strike:.0f}"
    if spot and spot > 0:
        pct = ((best_strike - spot) / spot) * 100
        label += f" ({pct:+.1f}% vs spot)"
    return {"max_pain": label}


def _compute_implied_move(contracts: list[dict[str, Any]], spot: float | None) -> dict[str, str] | None:
    """Compute the implied move from ATM straddle IV for the nearest expiry."""
    if not spot or spot <= 0:
        return None

    # Filter to nearest expiry with dte > 0
    with_dte = [c for c in contracts if c.get("dte") is not None and c["dte"] > 0]
    if not with_dte:
        return None

    min_dte = min(c["dte"] for c in with_dte)
    nearest = [c for c in with_dte if c["dte"] == min_dte]

    # Find ATM contracts (closest to spot)
    calls = sorted([c for c in nearest if c["type"] == "call"], key=lambda c: abs(c["strike"] - spot))
    puts = sorted([c for c in nearest if c["type"] == "put"], key=lambda c: abs(c["strike"] - spot))

    call_iv = calls[0]["iv"] if calls and calls[0].get("iv") is not None else None
    put_iv = puts[0]["iv"] if puts and puts[0].get("iv") is not None else None

    iv_candidates = [v for v in (call_iv, put_iv) if v is not None]
    if not iv_candidates:
        return None

    atm_iv = sum(iv_candidates) / len(iv_candidates)
    move_pct = atm_iv * math.sqrt(min_dte / 365)
    move_abs = spot * move_pct

    return {
        "implied_move": f"±{move_pct * 100:.1f}% (${move_abs:.2f}) over {min_dte}d",
        "expiry_window": f"nearest {min_dte}d",
    }


def _compute_gex(contracts: list[dict[str, Any]], spot: float | None) -> dict[str, str] | None:
    """Compute Gamma Exposure (GEX) — dealer perspective."""
    if not spot or spot <= 0:
        return None

    has_gamma = any(c.get("gamma") is not None for c in contracts)
    if not has_gamma:
        return None

    total_gex = 0.0
    for c in contracts:
        gamma = c.get("gamma")
        oi = c.get("oi", 0)
        if gamma is None or oi <= 0:
            continue
        # Per-contract GEX: gamma * OI * 100 shares * spot^2 * 0.01
        contract_gex = gamma * oi * 100 * spot * spot * 0.01
        # Dealer convention: long calls → short gamma for dealer (positive for market)
        # Actually: calls contribute positive GEX, puts contribute negative
        if c["type"] == "put":
            contract_gex = -contract_gex
        total_gex += contract_gex

    gex_millions = total_gex / 1e6
    if abs(gex_millions) < 50:
        regime = "flat"
    elif gex_millions > 0:
        regime = "positive"
    else:
        regime = "negative"

    return {"gex_regime": f"{regime} ${abs(gex_millions):.0f}M"}


def _compute_greeks_aggregates(contracts: list[dict[str, Any]]) -> dict[str, str]:
    """Aggregate Greeks across all contracts."""
    has_greeks = any(c.get("delta") is not None for c in contracts)
    if not has_greeks:
        return {}

    net_delta = 0.0
    total_gamma = 0.0
    weighted_theta = 0.0
    weighted_vega = 0.0
    total_oi = 0.0

    for c in contracts:
        oi = c.get("oi", 0)
        delta = c.get("delta")
        gamma = c.get("gamma")
        theta = c.get("theta")
        vega = c.get("vega")

        if delta is not None:
            net_delta += delta * oi * 100
        if gamma is not None:
            total_gamma += gamma * oi * 100
        if theta is not None:
            weighted_theta += theta * oi
            total_oi += oi
        if vega is not None:
            weighted_vega += vega * oi

    result: dict[str, str] = {}
    if net_delta != 0:
        result["net_delta"] = f"{int(net_delta):+,}"
    if total_gamma != 0:
        result["total_gamma"] = f"{int(total_gamma):,}"
    return result


def _compute_iv_skew(contracts: list[dict[str, Any]], spot: float | None) -> dict[str, str] | None:
    """Compute 25-delta put/call IV skew for the nearest expiry."""
    if not spot or spot <= 0:
        return None

    with_dte = [c for c in contracts if c.get("dte") is not None and c["dte"] > 0]
    if not with_dte:
        return None

    min_dte = min(c["dte"] for c in with_dte)
    nearest = [c for c in with_dte if c["dte"] == min_dte]

    target_delta = 0.25
    max_deviation = 0.15

    # Find 25-delta OTM put (delta ≈ -0.25)
    otm_puts = [c for c in nearest if c["type"] == "put" and c.get("delta") is not None and c.get("iv") is not None]
    otm_put = min(otm_puts, key=lambda c: abs(abs(c["delta"]) - target_delta), default=None) if otm_puts else None
    if otm_put and abs(abs(otm_put["delta"]) - target_delta) > max_deviation:
        otm_put = None

    # Find 25-delta OTM call (delta ≈ 0.25)
    otm_calls = [c for c in nearest if c["type"] == "call" and c.get("delta") is not None and c.get("iv") is not None]
    otm_call = min(otm_calls, key=lambda c: abs(c["delta"] - target_delta), default=None) if otm_calls else None
    if otm_call and abs(otm_call["delta"] - target_delta) > max_deviation:
        otm_call = None

    if not otm_put or not otm_call:
        return None

    skew = (otm_put["iv"] - otm_call["iv"]) * 100  # in percentage points
    bias = "fear-biased" if skew > 0 else "greed-biased" if skew < 0 else "neutral"
    return {"iv_skew": f"{skew:+.1f}pp ({bias})"}


def _compute_oi_concentration(contracts: list[dict[str, Any]], k: int = 3) -> dict[str, str]:
    """Find top OI strikes for calls and puts."""
    calls = [c for c in contracts if c["type"] == "call" and c["oi"] > 0]
    puts = [c for c in contracts if c["type"] == "put" and c["oi"] > 0]

    result: dict[str, str] = {}

    top_calls = sorted(calls, key=lambda c: c["oi"], reverse=True)[:k]
    if top_calls:
        result["top_call_oi"] = "; ".join(
            f"${c['strike']:.0f} (OI {c['oi'] / 1000:.1f}K)" for c in top_calls
        )

    top_puts = sorted(puts, key=lambda c: c["oi"], reverse=True)[:k]
    if top_puts:
        result["top_put_oi"] = "; ".join(
            f"${c['strike']:.0f} (OI {c['oi'] / 1000:.1f}K)" for c in top_puts
        )

    return result


def _compute_oi_ratio(contracts: list[dict[str, Any]]) -> dict[str, str]:
    """Position-based put/call OI ratio."""
    total_call_oi = sum(c["oi"] for c in contracts if c["type"] == "call")
    total_put_oi = sum(c["oi"] for c in contracts if c["type"] == "put")
    if total_call_oi <= 0:
        return {}
    ratio = total_put_oi / total_call_oi
    return {"put_call_oi_ratio": f"{ratio:.2f}"}


def _compute_unusual_activity_v2(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enhanced unusual activity: ranked by premium, with side info."""
    unusual: list[dict[str, Any]] = []
    for c in contracts:
        vol = c["volume"]
        oi = c["oi"]
        if vol <= 0 or oi <= 0 or vol <= oi * 5:
            continue

        mid = c.get("mid_price") or 0
        premium_usd = vol * mid * 100  # per contract = 100 shares

        unusual.append({
            "side": c["type"].upper(),
            "strike": c["strike"],
            "expiry": c.get("expiry"),
            "volume": vol,
            "oi": oi,
            "vol_oi_ratio": vol / oi if oi > 0 else 0,
            "premium_usd": premium_usd,
        })

    # Sort by premium descending (premium=0 fallback to vol/oi ratio)
    unusual.sort(key=lambda x: (x["premium_usd"], x["vol_oi_ratio"]), reverse=True)
    return unusual[:5]


# ── Main collector ──────────────────────────────────────────────────

def collect_options_flow(ticker: str, run_date: date) -> dict[str, str]:
    """Collect aggregated options flow data from Polygon.io.

    Returns a flat ``dict[str, str]`` with volume/OI basics plus
    Tier A metrics: max_pain, implied_move, gex_regime, greeks,
    iv_skew, oi_concentration, unusual_activity_v2.
    """
    try:
        data = _fetch_json(f"/v3/snapshot/options/{ticker}", {
            "limit": "50",
            "order": "desc",
            "sort": "ticker",
        })

        if not data or not isinstance(data, dict):
            return {}

        results_list = data.get("results", [])
        if not results_list:
            return {}

        # ── Phase 1: Parse ──
        contracts = _parse_contracts(results_list)
        if not contracts:
            return {}

        spot = _extract_spot_price(data)

        # ── Phase 2: Basic aggregates (preserve existing keys) ──
        result: dict[str, str] = {}

        total_call_volume = sum(c["volume"] for c in contracts if c["type"] == "call")
        total_put_volume = sum(c["volume"] for c in contracts if c["type"] == "put")

        if total_call_volume > 0 or total_put_volume > 0:
            result["net_call_volume"] = f"{int(total_call_volume):,}"
            result["net_put_volume"] = f"{int(total_put_volume):,}"

            if total_call_volume > 0:
                pc_ratio = total_put_volume / total_call_volume
                result["put_call_volume_ratio"] = f"{pc_ratio:.2f}"
                if pc_ratio > 1.5:
                    result["flow_sentiment"] = "bearish"
                elif pc_ratio < 0.5:
                    result["flow_sentiment"] = "bullish"
                else:
                    result["flow_sentiment"] = "neutral"

        iv_values = [c["iv"] for c in contracts if c.get("iv") is not None]
        if iv_values:
            result["avg_iv"] = f"{sum(iv_values) / len(iv_values) * 100:.1f}%"

        # ── Phase 3: Tier A metrics ──
        if spot:
            result["spot_price"] = f"${spot:.2f}"

        mp = _compute_max_pain(contracts, spot)
        if mp:
            result.update(mp)

        im = _compute_implied_move(contracts, spot)
        if im:
            result.update(im)

        gex = _compute_gex(contracts, spot)
        if gex:
            result.update(gex)

        greeks = _compute_greeks_aggregates(contracts)
        if greeks:
            result.update(greeks)

        skew = _compute_iv_skew(contracts, spot)
        if skew:
            result.update(skew)

        oi_conc = _compute_oi_concentration(contracts)
        if oi_conc:
            result.update(oi_conc)

        oi_r = _compute_oi_ratio(contracts)
        if oi_r:
            result.update(oi_r)

        # Enhanced unusual activity (replaces basic version)
        unusual_v2 = _compute_unusual_activity_v2(contracts)
        if unusual_v2:
            parts: list[str] = []
            for u in unusual_v2:
                prem_label = f"prem=${u['premium_usd'] / 1000:.0f}K" if u["premium_usd"] >= 1000 else f"prem=${u['premium_usd']:.0f}"
                parts.append(f"{u['side']} ${u['strike']:.0f} vol={int(u['volume'])} {prem_label}")
            result["unusual_activity"] = "; ".join(parts)

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


# ── Shared helper ───────────────────────────────────────────────────

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        return None if f != f else f  # NaN check
    except (TypeError, ValueError):
        return None
