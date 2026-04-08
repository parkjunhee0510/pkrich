from __future__ import annotations

from datetime import date
from time import sleep

from src.types import CollectedTickerData, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection


def collect_market_data(
    watchlist: list[WatchlistItem],
    run_date: date,
) -> dict[str, CollectedTickerData]:
    results: dict[str, CollectedTickerData] = {}

    for item in watchlist:
        results[item.ticker] = _collect_single_ticker(item, run_date)
        sleep(0.1)

    return results


def _collect_single_ticker(
    item: WatchlistItem,
    run_date: date,
) -> CollectedTickerData:
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=False):
        return _fallback_market_data(item, "External fetch disabled; skipped Yahoo Finance request.")

    if not can_open_tcp_connection("query1.finance.yahoo.com", 443):
        return _fallback_market_data(item, "Network unavailable; skipped Yahoo Finance request.")

    try:
        import yfinance as yf  # type: ignore

        ticker = yf.Ticker(item.ticker)
        history = ticker.history(period="5d", interval="1d")
        info = getattr(ticker, "info", {}) or {}

        if not history.empty and "Close" in history and len(history["Close"]) >= 1:
            latest_close = float(history["Close"].iloc[-1])
            previous_close = float(history["Close"].iloc[-2]) if len(history["Close"]) > 1 else latest_close
            change_percent = ((latest_close - previous_close) / previous_close * 100) if previous_close else 0.0
        else:
            latest_close = None
            change_percent = None

        return CollectedTickerData(
            ticker=item.ticker,
            name=item.name,
            sector=item.sector,
            price=latest_close,
            change_percent=change_percent,
            currency=str(info.get("currency", "USD")),
            market_cap=_format_large_number(info.get("marketCap")),
            pe_ratio=_format_ratio(info.get("trailingPE")),
            summary_note=f"Collected market data on {run_date.isoformat()}",
        )
    except Exception:
        return _fallback_market_data(item, "Market data unavailable; using graceful fallback.")


def _fallback_market_data(item: WatchlistItem, summary_note: str) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=item.ticker,
        name=item.name,
        sector=item.sector,
        price=None,
        change_percent=None,
        currency="USD",
        market_cap="N/A",
        pe_ratio="N/A",
        summary_note=summary_note,
    )


def _format_large_number(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value:.0f}"


def _format_ratio(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    return f"{value:.2f}"
