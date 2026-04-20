"""Sector explorer collector — price + news only, no LLM, no decision layer.

Strictly read-only telemetry for the `/sectors` page in the React frontend.
Deliberately scoped narrower than `src/collector/price.py`:

  - No FMP / SEC / Finnhub / options / insider flow.
  - No analyst estimates / institutional holders / technical indicators.
  - Just: current price, 6-month daily history, and a small news list.

The collector accepts an optional `skip_tickers` set so tickers that already
live in the main watchlist reuse that data and don't double-call yfinance.

Output is a plain dataclass (`SectorTickerSnapshot`) per ticker plus a
`SectorSnapshot` wrapper per sector, ready for `src/output/sectors_json.py`
to serialize.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable

from src.types import NewsItem, WatchlistItem
from src.utils.config import SectorConfig, SectorTickerConfig
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event


@dataclass(frozen=True)
class SectorPricePoint:
    """Single (date, close) point for the sparkline/chart."""
    date: str
    close: float


@dataclass(frozen=True)
class SectorTickerSnapshot:
    """All data the frontend needs to render one card inside a sector view."""
    ticker: str
    name: str
    price: str  # formatted "18.50 USD" (empty string when unavailable)
    currency: str
    change_percent: str  # "+2.3%" or empty
    history: list[SectorPricePoint] = field(default_factory=list)
    news: list[NewsItem] = field(default_factory=list)
    error: str = ""  # populated when collection failed for this ticker


@dataclass(frozen=True)
class SectorBenchmark:
    """Benchmark ETF series accompanying a sector (optional)."""
    ticker: str
    name: str
    price: str
    currency: str
    change_percent: str
    history: list[SectorPricePoint] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class SectorSnapshot:
    """One sector's full payload."""
    id: str
    name: str
    description: str
    tickers: list[SectorTickerSnapshot] = field(default_factory=list)
    benchmark: SectorBenchmark | None = None


def scan_sectors(
    sectors: Iterable[SectorConfig],
    run_date: date,
    *,
    skip_tickers: set[str] | None = None,
) -> list[SectorSnapshot]:
    """Collect price + news for every ticker in `sectors`.

    `skip_tickers` lists tickers already covered by the main watchlist —
    they are still rendered on the page (via reuse from the caller), but the
    scan short-circuits to avoid hammering yfinance twice. Callers can merge
    skip-ticker data back in when building `sectors.json`.
    """
    skip = {t.upper() for t in (skip_tickers or set())}
    external_enabled = is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True)
    yfinance_ready = external_enabled and can_open_tcp_connection(
        "query1.finance.yahoo.com", 443
    )

    results: list[SectorSnapshot] = []
    for sector in sectors:
        ticker_snapshots: list[SectorTickerSnapshot] = []
        for item in sector.tickers:
            if item.ticker.upper() in skip:
                # Caller will populate from watchlist cache. Emit a sentinel
                # so the sector retains the slot in the rendered order.
                ticker_snapshots.append(
                    SectorTickerSnapshot(
                        ticker=item.ticker,
                        name=item.name,
                        price="",
                        currency="",
                        change_percent="",
                        error="reuse_from_watchlist",
                    )
                )
                continue
            snapshot = _collect_sector_ticker(
                item,
                sector.news_keywords,
                run_date,
                yfinance_ready=yfinance_ready,
                external_enabled=external_enabled,
            )
            ticker_snapshots.append(snapshot)

        benchmark = _collect_benchmark(
            sector.benchmark_etf, yfinance_ready=yfinance_ready
        )

        results.append(
            SectorSnapshot(
                id=sector.id,
                name=sector.name,
                description=sector.description,
                tickers=ticker_snapshots,
                benchmark=benchmark,
            )
        )
    return results


def _collect_benchmark(etf_symbol: str, *, yfinance_ready: bool) -> SectorBenchmark | None:
    """Fetch the sector's benchmark ETF. Returns None when unconfigured or
    the network is offline -- the frontend gracefully drops the overlay."""
    if not etf_symbol:
        return None
    if not yfinance_ready:
        return SectorBenchmark(
            ticker=etf_symbol,
            name=etf_symbol,
            price="",
            currency="",
            change_percent="",
            error="network_unavailable",
        )
    try:
        price_str, currency, change_str, history = _fetch_yfinance_snapshot(etf_symbol)
    except Exception as exc:  # noqa: BLE001 -- defensive
        record_pipeline_event(
            "collector",
            "warning",
            "sector_benchmark_failed",
            ticker=etf_symbol,
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
        return SectorBenchmark(
            ticker=etf_symbol,
            name=etf_symbol,
            price="",
            currency="",
            change_percent="",
            error="fetch_failed",
        )
    return SectorBenchmark(
        ticker=etf_symbol,
        name=etf_symbol,
        price=price_str,
        currency=currency,
        change_percent=change_str,
        history=history,
    )


def _collect_sector_ticker(
    item: SectorTickerConfig,
    sector_keywords: list[str],
    run_date: date,
    *,
    yfinance_ready: bool,
    external_enabled: bool,
) -> SectorTickerSnapshot:
    """Fetch price + history + news for a single sector ticker."""
    price_str = ""
    currency = "USD"
    change_str = ""
    history: list[SectorPricePoint] = []

    if yfinance_ready:
        try:
            price_str, currency, change_str, history = _fetch_yfinance_snapshot(
                item.ticker
            )
        except Exception as exc:  # defensive — collection must never crash pipeline
            record_pipeline_event(
                "collector",
                "warning",
                "sector_price_failed",
                ticker=item.ticker,
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )

    news = _collect_sector_news(
        item, sector_keywords, run_date, external_enabled=external_enabled
    )

    return SectorTickerSnapshot(
        ticker=item.ticker,
        name=item.name,
        price=price_str,
        currency=currency,
        change_percent=change_str,
        history=history,
        news=news,
    )


def _fetch_yfinance_snapshot(ticker: str) -> tuple[str, str, str, list[SectorPricePoint]]:
    """Minimal yfinance call: spot price + 1y close series. No info-dict pulls.

    Returns (price_display, currency, change_display, history). 1-year window
    enables 52-week high/low positioning in the frontend; still one call per
    ticker, so total pipeline cost is unchanged. When yfinance returns
    partial data, fields fall back to empty strings rather than raising --
    `_collect_sector_ticker` logs the outer failure instead.
    """
    import yfinance as yf  # type: ignore

    handle = yf.Ticker(ticker)
    # auto_adjust=True matches `collector/price.py` so chart bases stay
    # consistent across the app.
    hist = handle.history(period="1y", interval="1d", auto_adjust=True)
    info = getattr(handle, "info", {}) or {}
    currency = str(info.get("currency", "USD") or "USD")

    history: list[SectorPricePoint] = []
    try:
        for idx, row in hist.iterrows():  # type: ignore[attr-defined]
            close_value = row.get("Close")
            if close_value is None:
                continue
            try:
                close_float = float(close_value)
            except (TypeError, ValueError):
                continue
            if close_float != close_float:  # NaN guard
                continue
            history.append(
                SectorPricePoint(
                    date=str(idx.date()) if hasattr(idx, "date") else str(idx)[:10],
                    close=round(close_float, 4),
                )
            )
    except Exception:
        history = []

    price_display = ""
    change_display = ""
    if history:
        latest_close = history[-1].close
        price_display = f"{latest_close:.2f} {currency}"
        if len(history) >= 2:
            prev_close = history[-2].close
            if prev_close:
                pct = (latest_close - prev_close) / prev_close * 100
                sign = "+" if pct >= 0 else ""
                change_display = f"{sign}{pct:.2f}%"

    return price_display, currency, change_display, history


def _collect_sector_news(
    item: SectorTickerConfig,
    sector_keywords: list[str],
    run_date: date,
    *,
    external_enabled: bool,
) -> list[NewsItem]:
    """Reuse the Google News RSS collector by adapting the sector ticker into
    a lightweight `WatchlistItem`. No SEC/IR feeds — those require CIK and
    curated IR sources, which the sector explorer deliberately omits."""
    if not external_enabled:
        return []

    try:
        from src.collector.news_rss import _collect_rss_news
    except ImportError:
        return []

    keywords = list(sector_keywords)
    # Make sure the ticker name itself is searchable — avoids topic-only drift
    # (e.g. "rocket" without "Rocket Lab" returning sector-level noise).
    if item.name and item.name not in keywords:
        keywords = [item.name, *keywords]

    adapter = WatchlistItem(
        ticker=item.ticker,
        name=item.name,
        sector="",
        keywords=keywords,
    )

    try:
        google_available = can_open_tcp_connection("news.google.com", 443)
        raw = _collect_rss_news(adapter, google_available)
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "sector_news_failed",
            ticker=item.ticker,
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
        return []

    # Trim: the frontend renders ~5 headlines per card.
    cutoff = run_date - timedelta(days=30)
    filtered: list[NewsItem] = []
    for entry in raw:
        published = str(entry.published_at or "").strip()[:10]
        if published:
            try:
                published_date = date.fromisoformat(published)
                if published_date < cutoff:
                    continue
            except ValueError:
                pass
        filtered.append(entry)
        if len(filtered) >= 5:
            break
    return filtered
