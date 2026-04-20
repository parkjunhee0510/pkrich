"""Orchestrated-path adapters that match the legacy function signatures.

This is the seam between `pipeline.py` and the new plugin architecture.
`pipeline.py` always calls the same function names (`collect_market_data`,
`collect_news_for_watchlist`). When the feature flags are enabled, those
calls route through this module — which assembles the orchestrator(s),
runs them, and returns the result in the legacy shape.

Having ONE adapter module (instead of orchestrator-assembly sprinkled
across shadow_compare, pipeline, etc.) means:
  * Provider lists live in one place — no drift between primary and shadow.
  * pipeline.py stays narrow: it dispatches on the flag, nothing more.
  * Future Step 5b (legacy retirement) just deletes the legacy branch;
    this module becomes the only path.
"""
from __future__ import annotations

import logging
import os
from datetime import date

from src.collector.bootstrap import build_orchestrator
from src.collector.news_orchestrator import NewsOrchestrator
from src.collector.news_shadow_compare import build_news_orchestrator
from src.collector.orchestrator import CollectionOrchestrator
from src.collector.providers.alphavantage_provider import AlphaVantageProvider
from src.collector.providers.finnhub_provider import FinnhubProvider
from src.collector.providers.fmp_provider import FMPProvider
from src.collector.providers.polygon_provider import PolygonProvider
from src.collector.providers.sector_etf_provider import SectorEtfProvider
from src.collector.providers.stooq_provider import StooqProvider
from src.collector.providers.yfinance_provider import YFinanceProvider
from src.types import CollectedTickerData, NewsItem, WatchlistItem
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)


# Phase 1-1 defaults. 4 workers balance yfinance's historical thread-safety
# concerns (per-Ticker instance is safe, but shared session state was not)
# against meaningful throughput gains. 50-ticker watchlists still finish in
# roughly 60% of the sequential runtime.
_DEFAULT_MAX_WORKERS = 4


def _resolve_max_workers(override: int | None) -> int:
    """Resolve the worker count for the market orchestrator.

    Resolution order:
      1. Explicit `override` argument (tests, callers that need a specific value).
      2. `COLLECTOR_MAX_WORKERS` environment variable.
      3. `_DEFAULT_MAX_WORKERS`.

    Invalid env values fall back to the default with a warning.
    """
    if override is not None:
        return max(1, override)

    raw = os.getenv("COLLECTOR_MAX_WORKERS")
    if raw is None or raw.strip() == "":
        return _DEFAULT_MAX_WORKERS
    try:
        parsed = int(raw.strip())
    except ValueError:
        logger.warning(
            "Invalid COLLECTOR_MAX_WORKERS=%r — falling back to default %d",
            raw, _DEFAULT_MAX_WORKERS,
        )
        return _DEFAULT_MAX_WORKERS
    if parsed < 1:
        logger.warning(
            "COLLECTOR_MAX_WORKERS=%d must be >= 1 — falling back to default %d",
            parsed, _DEFAULT_MAX_WORKERS,
        )
        return _DEFAULT_MAX_WORKERS
    return parsed


def build_full_orchestrator(
    *,
    benchmark_change_30d: float | None = None,
    max_workers: int | None = None,
) -> CollectionOrchestrator:
    """Construct the production CollectionOrchestrator with all providers.

    Priority order (via each provider's `priority` class attribute):
      1. YFinance      — primary price/fundamentals
      2. FMP           — fundamentals / insider / analyst
      2. Finnhub       — analyst recommendation trends
      2. Polygon       — options flow (Starter plan)
      3. AlphaVantage  — fundamentals/earnings fallback
      3. Stooq         — price fallback

    Lower `priority` value wins during merge. `benchmark_change_30d` is
    passed through to YFinance so the RS-vs-SPY calculation works.

    `max_workers` enables Phase 1-1 parallel ticker collection when > 1.
    """
    return build_orchestrator(
        providers=[
            YFinanceProvider(benchmark_change_30d=benchmark_change_30d),
            SectorEtfProvider(),
            FMPProvider(),
            FinnhubProvider(),
            PolygonProvider(),
            AlphaVantageProvider(),
            StooqProvider(),
        ],
        max_workers=max_workers,
    )


def collect_market_data_via_orchestrator(
    watchlist: list[WatchlistItem],
    run_date: date,
    *,
    benchmark_change_30d: float | None = None,
    max_workers: int | None = None,
) -> dict[str, CollectedTickerData]:
    """Orchestrator-backed drop-in replacement for `collect_market_data()`.

    Runs the full 6-provider orchestrator and returns only the
    `dict[ticker, CollectedTickerData]` portion — the legacy shape
    pipeline.py already consumes. The diagnostic report is logged via
    `record_pipeline_event` instead of returned, so the caller's
    signature is unchanged.

    Parallelism: defaults to `_DEFAULT_MAX_WORKERS` (4) threads, overridable
    by the `COLLECTOR_MAX_WORKERS` env var or the `max_workers` argument.
    """
    workers = _resolve_max_workers(max_workers)
    orchestrator = build_full_orchestrator(
        benchmark_change_30d=benchmark_change_30d,
        max_workers=workers,
    )
    collected, report = orchestrator.collect_all(watchlist, run_date)

    # Surface the diagnostic counts the legacy path can't provide.
    record_pipeline_event(
        "collector", "info", "orchestrator_primary_completed",
        tickers_total=len(watchlist),
        providers_used=sorted(report.providers_used()),
        failures=report.failure_count(),
        duration_ms=report.total_duration_ms,
        max_workers=workers,
    )
    return collected


def collect_news_via_orchestrator(
    watchlist: list[WatchlistItem],
    run_date: date,
    *,
    orchestrator: NewsOrchestrator | None = None,
) -> dict[str, list[NewsItem]]:
    """Orchestrator-backed drop-in replacement for `collect_news_for_watchlist()`.

    Uses the same 4-provider NewsOrchestrator that shadow mode uses
    (SEC EDGAR / IR RSS / Google News / DuckDuckGo). The report is
    logged rather than returned, matching the legacy function shape.
    """
    orch = orchestrator or build_news_orchestrator()
    per_ticker, report = orch.collect_all(watchlist, run_date)

    record_pipeline_event(
        "collector", "info", "news_orchestrator_primary_completed",
        tickers_total=len(watchlist),
        total_items=report.total_items(),
        provider_failures=len(report.provider_failures),
        per_provider_counts=dict(report.per_provider_counts),
    )
    return per_ticker


__all__ = [
    "build_full_orchestrator",
    "collect_market_data_via_orchestrator",
    "collect_news_via_orchestrator",
]
