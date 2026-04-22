"""Compute ticker-level macro factor betas (rates / USD / oil / credit).

Uses ~60 days of daily returns and a simple OLS against a small set of macro
driver return series. Results degrade gracefully to sector-average proxies if
price history is insufficient.

The module exposes two entry points:

- ``fetch_macro_driver_returns()`` — fetch & cache the driver return series
  for the current run. Returns a dict of driver_name -> pandas.Series.
- ``compute_ticker_macro_betas(ticker, driver_returns)`` — given the cached
  driver returns, compute one set of betas for ``ticker``.

The functions are intentionally tolerant: any yfinance failure produces an
empty result so decision/analysis layers can fall back to the sector proxy.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from src.utils.network import can_open_tcp_connection

logger = logging.getLogger(__name__)

_DRIVER_SYMBOLS: dict[str, str] = {
    "rates": "^TNX",    # US 10Y yield
    "usd": "DX-Y.NYB",  # Dollar Index
    "oil": "CL=F",      # WTI
    "credit": "HYG",    # High-yield ETF (proxies risk premium)
}

_MIN_SAMPLES = 40
_LOOKBACK_PERIOD = "90d"

_SECTOR_BETA_PROXY: dict[str, dict[str, float]] = {
    "technology": {"rates": -0.25, "usd": -0.10, "oil": 0.05, "credit": 0.55},
    "communication": {"rates": -0.15, "usd": -0.05, "oil": 0.02, "credit": 0.40},
    "consumer cyclical": {"rates": -0.20, "usd": -0.10, "oil": -0.05, "credit": 0.60},
    "consumer discretionary": {"rates": -0.20, "usd": -0.10, "oil": -0.05, "credit": 0.60},
    "financial": {"rates": 0.20, "usd": 0.05, "oil": 0.00, "credit": 0.50},
    "industrial": {"rates": 0.05, "usd": -0.05, "oil": 0.10, "credit": 0.55},
    "energy": {"rates": 0.05, "usd": -0.20, "oil": 0.70, "credit": 0.45},
    "material": {"rates": 0.00, "usd": -0.20, "oil": 0.25, "credit": 0.50},
    "real estate": {"rates": -0.35, "usd": 0.00, "oil": 0.00, "credit": 0.50},
    "utilit": {"rates": -0.30, "usd": 0.00, "oil": 0.05, "credit": 0.20},
    "staples": {"rates": -0.10, "usd": 0.05, "oil": 0.00, "credit": 0.20},
    "consumer defensive": {"rates": -0.10, "usd": 0.05, "oil": 0.00, "credit": 0.20},
    "health": {"rates": -0.10, "usd": 0.00, "oil": 0.00, "credit": 0.30},
}

_cache_lock = threading.Lock()
_driver_returns_cache: dict[str, Any] | None = None


def fetch_macro_driver_returns(force_refresh: bool = False) -> dict[str, Any]:
    """Return cached driver return series keyed by driver name.

    Empty dict when yfinance/network is unavailable.
    """
    global _driver_returns_cache
    with _cache_lock:
        if _driver_returns_cache is not None and not force_refresh:
            return _driver_returns_cache

    if not can_open_tcp_connection("query1.finance.yahoo.com", 443):
        return {}

    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return {}

    results: dict[str, Any] = {}
    for driver, symbol in _DRIVER_SYMBOLS.items():
        try:
            hist = yf.Ticker(symbol).history(period=_LOOKBACK_PERIOD, interval="1d")
            if hist is None or hist.empty:
                continue
            close = hist["Close"].dropna()
            if len(close) < _MIN_SAMPLES:
                continue
            returns = close.pct_change().dropna()
            if not returns.empty:
                results[driver] = returns
        except Exception:
            logger.debug("driver %s fetch failed", driver, exc_info=True)

    with _cache_lock:
        _driver_returns_cache = results
    return results


def compute_ticker_macro_betas(
    ticker: str,
    driver_returns: dict[str, Any],
    *,
    sector: str = "",
) -> dict[str, Any]:
    """Compute betas for ``ticker`` or fall back to sector proxies.

    Returned dict keys: ``rates_beta``, ``usd_beta``, ``oil_beta``,
    ``credit_beta``, ``source`` ("ols"|"sector_proxy"|"unknown"),
    ``r2``, ``samples``.
    """
    fallback = _sector_proxy(sector)

    if not driver_returns or not can_open_tcp_connection("query1.finance.yahoo.com", 443):
        return fallback

    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return fallback

    try:
        hist = yf.Ticker(ticker).history(period=_LOOKBACK_PERIOD, interval="1d")
        if hist is None or hist.empty:
            return fallback
        close = hist["Close"].dropna()
        if len(close) < _MIN_SAMPLES:
            return fallback
        ticker_returns = close.pct_change().dropna()
    except Exception:
        logger.debug("ticker %s history fetch failed", ticker, exc_info=True)
        return fallback

    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
    except Exception:
        return fallback

    frames: dict[str, Any] = {"y": ticker_returns}
    for name, series in driver_returns.items():
        frames[name] = series
    df = pd.DataFrame(frames).dropna()
    if len(df) < _MIN_SAMPLES:
        return fallback

    drivers = [c for c in df.columns if c != "y"]
    y = df["y"].to_numpy()
    X = df[drivers].to_numpy()
    X = np.column_stack([np.ones(len(X)), X])

    try:
        coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
        preds = X @ coeffs
        resid = y - preds
        ss_res = float((resid ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    except Exception:
        return fallback

    # coeffs[0] is intercept; drivers follow.
    betas: dict[str, Any] = {}
    for idx, name in enumerate(drivers, start=1):
        betas[f"{name}_beta"] = round(float(coeffs[idx]), 4)

    # Ensure all standard keys present.
    for required in ("rates", "usd", "oil", "credit"):
        betas.setdefault(f"{required}_beta", fallback.get(f"{required}_beta", 0.0))

    betas["r2"] = round(r2, 3)
    betas["samples"] = len(df)
    betas["source"] = "ols" if r2 >= 0.05 else "ols_low_r2"
    return betas


def build_ticker_macro_snapshot(
    betas: dict[str, Any],
    macro_context: dict[str, Any],
) -> str:
    """Produce a short Korean narrative using current macro drivers × betas."""
    if not betas:
        return ""

    parts: list[str] = []
    driver_moves = _recent_driver_moves(macro_context)
    for driver, change_pct in driver_moves.items():
        beta = _as_float(betas.get(f"{driver}_beta"))
        if beta is None or abs(beta) < 0.05 or abs(change_pct) < 0.1:
            continue
        est = beta * change_pct
        if abs(est) < 0.1:
            continue
        parts.append(
            f"{driver.upper()} {change_pct:+.2f}% × β{beta:+.2f} ≈ {est:+.2f}%"
        )
    if not parts:
        return ""
    r2 = betas.get("r2")
    tail = f" (R²={r2})" if r2 is not None else ""
    return "최근 드라이버 영향: " + " | ".join(parts[:4]) + tail


def _recent_driver_moves(macro_context: dict[str, Any]) -> dict[str, float]:
    mapping = {
        "rates": "us10y",
        "usd": "dxy",
        "oil": "oil_wti",
        "credit": "hyg",
    }
    moves: dict[str, float] = {}
    for driver, context_key in mapping.items():
        block = macro_context.get(context_key, {})
        if not isinstance(block, dict):
            continue
        value = _as_float(block.get("change"))
        if value is not None:
            moves[driver] = value
    return moves


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _sector_proxy(sector: str) -> dict[str, Any]:
    sector_lower = (sector or "").strip().lower()
    for key, row in _SECTOR_BETA_PROXY.items():
        if key and key in sector_lower:
            out = {f"{k}_beta": v for k, v in row.items()}
            out["source"] = "sector_proxy"
            out["samples"] = 0
            out["r2"] = None
            return out
    return {
        "rates_beta": 0.0,
        "usd_beta": 0.0,
        "oil_beta": 0.0,
        "credit_beta": 0.0,
        "source": "unknown",
        "samples": 0,
        "r2": None,
    }
