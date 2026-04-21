"""YFinance-based peer metrics collector.

Fallback/primary source for peer comparison metrics when FMP plan-limited
endpoints (stable/key-metrics, stable/financial-ratios) are unavailable.

Covers the fields consumed by ``build_peer_rank``:
  * pe_ratio, roe, gross_margin
  * price_change_30d
  * revenue_growth
  * dividend_yield
  * market_cap, avg_volume, sector

All free — uses the public yfinance `.info` and 2-month history endpoints.
"""
from __future__ import annotations

from typing import Any

from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event


def is_yfinance_peer_ready() -> bool:
    return can_open_tcp_connection("finance.yahoo.com", 443)


def collect_yfinance_peer_metrics(tickers: list[str]) -> dict[str, dict[str, str]]:
    """Fetch peer metrics for a list of tickers via yfinance.

    Returns dict keyed by ticker with formatted string metrics.
    Tickers that fail silently produce no entry (upstream handles absence).
    """
    if not tickers:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        record_pipeline_event(
            "collector", "warning", "yfinance_peer_metrics_missing_dep",
            count=len(tickers),
        )
        return {}

    result: dict[str, dict[str, str]] = {}
    for ticker in tickers:
        try:
            handle = yf.Ticker(ticker)
            info = handle.info or {}
            metrics = _extract_metrics(info)
            change_30d = _compute_30d_change(handle)
            if change_30d is not None:
                metrics["price_change_30d"] = f"{change_30d:+.2f}%"
            if metrics:
                result[ticker] = metrics
                record_pipeline_event(
                    "collector", "info", "yfinance_peer_metrics",
                    ticker=ticker, fields=len(metrics),
                )
        except Exception as exc:  # noqa: BLE001 — best-effort across many tickers
            record_pipeline_event(
                "collector", "warning", "yfinance_peer_metrics_failed",
                ticker=ticker, error=str(exc)[:200],
            )
            continue
    return result


def _extract_metrics(info: dict[str, Any]) -> dict[str, str]:
    metrics: dict[str, str] = {}

    sector = info.get("sector")
    if isinstance(sector, str) and sector.strip():
        metrics["sector"] = sector.strip()

    market_cap = _safe_float(info.get("marketCap"))
    if market_cap is not None and market_cap > 0:
        metrics["market_cap"] = f"{market_cap:.0f}"

    avg_volume = _safe_float(info.get("averageVolume") or info.get("averageDailyVolume10Day"))
    if avg_volume is not None and avg_volume > 0:
        metrics["avg_volume"] = f"{avg_volume:.0f}"

    pe = _safe_float(info.get("trailingPE") or info.get("forwardPE"))
    if pe is not None and pe > 0:
        metrics["pe_ratio"] = f"{pe:.2f}x"

    roe = _safe_float(info.get("returnOnEquity"))
    if roe is not None:
        metrics["roe"] = _format_percent_from_decimal(roe)

    gross_margin = _safe_float(info.get("grossMargins"))
    if gross_margin is not None:
        metrics["gross_margin"] = _format_percent_from_decimal(gross_margin)

    revenue_growth = _safe_float(
        info.get("revenueGrowth") if info.get("revenueGrowth") is not None else info.get("earningsGrowth")
    )
    if revenue_growth is not None:
        metrics["revenue_growth"] = _format_percent_from_decimal(revenue_growth)

    # yfinance `dividendYield` is unreliable (mixes decimal/percent across
    # tickers). Compute from dividendRate / currentPrice for consistency.
    dividend_rate = _safe_float(info.get("dividendRate") or info.get("trailingAnnualDividendRate"))
    current_price = _safe_float(
        info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    )
    if dividend_rate is not None and dividend_rate > 0 and current_price and current_price > 0:
        yield_pct = dividend_rate / current_price * 100.0
        if 0 < yield_pct < 50:  # sanity band
            metrics["dividend_yield"] = f"{yield_pct:.2f}%"

    return metrics


def _compute_30d_change(handle: Any) -> float | None:
    try:
        hist = handle.history(period="2mo", interval="1d", auto_adjust=False)
    except Exception:
        return None
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    closes = hist["Close"].dropna()
    if len(closes) < 2:
        return None
    latest = _safe_float(closes.iloc[-1])
    # ~30 trading days earlier, or earliest if series shorter
    reference_idx = -22 if len(closes) >= 22 else 0
    reference = _safe_float(closes.iloc[reference_idx])
    if latest is None or reference is None or reference == 0:
        return None
    return (latest - reference) / reference * 100.0


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN check
        return None
    return result


def _format_percent_from_decimal(value: float) -> str:
    """yfinance returns ratios as decimals (0.15) or already-percent (15.0)
    depending on field. Heuristic: magnitude < 10 → decimal.
    """
    if abs(value) < 10:
        return f"{value * 100:.1f}%"
    return f"{value:.1f}%"
