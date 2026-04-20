"""Collection Orchestrator — runs all DataProviders against a watchlist.

Responsibilities:
  1. For each ticker, invoke every registered provider in priority order.
  2. Rate-limit each provider via the RateLimiterHub.
  3. Short-circuit with cache hits (configurable TTL per data type).
  4. Merge PartialTickerData results into one CollectedTickerData.
     Merge rule: the first non-None value wins. Because providers are
     iterated in ascending priority order, priority 1 data takes precedence
     over priority 2 fallback data automatically.
  5. Collect diagnostics (ProviderResult list) for observability.

Parallelism (Phase 1-1):
  When `max_workers > 1`, tickers are collected concurrently via a
  `ThreadPoolExecutor`. Provider execution WITHIN a ticker remains
  sequential so the merge order (by priority) stays deterministic.
  The rate limiter (token bucket, thread-safe) and ResponseCache
  (sqlite3 with `check_same_thread=False` plus internal lock) already
  tolerate concurrent access, so no other changes were required.

Note: This module runs *alongside* the legacy `collect_market_data()`
path during the migration. Pipeline integration (Step 3 of 1-0e) will
switch the pipeline to call `CollectionOrchestrator.collect_all()`.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
)
from src.collector.cache import ResponseCache
from src.collector.rate_limiter import RateLimiterHub
from src.collector.registry import ProviderRegistry
from src.types import CollectedTickerData, WatchlistItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache TTL policy — which data types can safely use cached results.
# Values are hours. Unlisted types default to 0 (no caching).
# These are deliberately conservative; tune after observing cache hit rates.
# ---------------------------------------------------------------------------
DEFAULT_CACHE_TTL_HOURS: dict[str, float] = {
    "fundamentals": 24.0,
    "quarterly_financials": 24.0,
    "upcoming_events": 6.0,
    "sec_filings": 12.0,
    "ir_rss": 6.0,
    "institutional_holdings": 168.0,  # weekly
    "analyst_estimates": 24.0,
    # Intentionally omitted (too volatile for caching):
    #   price, technicals, options, news, historical_prices
}


@dataclass(frozen=True)
class OrchestrationReport:
    """Per-run diagnostics. Pipeline logs this for observability."""
    results_by_ticker: dict[str, list[ProviderResult]] = field(default_factory=dict)
    total_duration_ms: int = 0

    def providers_used(self) -> set[str]:
        seen: set[str] = set()
        for results in self.results_by_ticker.values():
            for r in results:
                if r.ok:
                    seen.add(r.provider)
        return seen

    def failure_count(self) -> int:
        return sum(
            1
            for results in self.results_by_ticker.values()
            for r in results
            if r.status == "failure"
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class CollectionOrchestrator:
    """Runs registered providers across a watchlist and merges outputs.

    Typical usage:
        registry = ProviderRegistry()
        registry.register(YFinanceProvider())
        registry.register(FMPProvider())

        rate_hub = RateLimiterHub()
        for p in registry.all():
            rate_hub.register(p.name, p.rate_limit)

        orchestrator = CollectionOrchestrator(
            registry=registry,
            rate_hub=rate_hub,
            cache=ResponseCache(),
        )
        collected, report = orchestrator.collect_all(watchlist, run_date)
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        rate_hub: RateLimiterHub | None = None,
        cache: ResponseCache | None = None,
        cache_ttl_hours: dict[str, float] | None = None,
        max_workers: int | None = None,
    ) -> None:
        self._registry = registry
        self._rate_hub = rate_hub or RateLimiterHub()
        self._cache = cache
        self._cache_ttl = cache_ttl_hours or DEFAULT_CACHE_TTL_HOURS
        # Phase 1-1: parallel ticker collection. None or 1 → sequential.
        # Values > 1 enable ThreadPoolExecutor across tickers. Rate limiter
        # and cache are already thread-safe; provider execution within a
        # ticker stays sequential so merge order remains deterministic.
        if max_workers is not None and max_workers < 1:
            raise ValueError(f"max_workers must be >= 1 (got {max_workers})")
        self._max_workers = max_workers

        # Ensure every provider is registered with the rate hub.
        for provider in registry.all():
            self._rate_hub.register(provider.name, provider.rate_limit)

    # --------------------------- public API ---------------------------
    def collect_all(
        self,
        watchlist: list[WatchlistItem],
        run_date: date,
    ) -> tuple[dict[str, CollectedTickerData], OrchestrationReport]:
        """Collect data for every watchlist item.

        Returns (collected_by_ticker, report). The report is intentionally
        separate so callers can log it without mutating collection state.
        """
        start = time.monotonic()
        collected: dict[str, CollectedTickerData] = {}
        results_by_ticker: dict[str, list[ProviderResult]] = {}

        # Choose execution mode. Parallel requires >1 workers AND >1 ticker
        # (pointless overhead otherwise).
        parallel = (
            self._max_workers is not None
            and self._max_workers > 1
            and len(watchlist) > 1
        )

        if parallel:
            # Bound worker count to ticker count so we don't spawn idle threads.
            workers = min(self._max_workers, len(watchlist))  # type: ignore[type-var]
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="collect") as pool:
                futures = {
                    pool.submit(self._collect_for_ticker, item, run_date): item
                    for item in watchlist
                }
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        ticker_data, ticker_results = future.result()
                    except Exception as err:  # noqa: BLE001 — defensive; _collect_for_ticker shouldn't raise.
                        logger.exception(
                            "Parallel collection raised for %s: %s — skipping ticker",
                            item.ticker, err,
                        )
                        continue
                    collected[item.ticker] = ticker_data
                    results_by_ticker[item.ticker] = ticker_results
        else:
            for item in watchlist:
                ticker_data, ticker_results = self._collect_for_ticker(item, run_date)
                collected[item.ticker] = ticker_data
                results_by_ticker[item.ticker] = ticker_results

        duration_ms = int((time.monotonic() - start) * 1000)
        report = OrchestrationReport(
            results_by_ticker=results_by_ticker,
            total_duration_ms=duration_ms,
        )
        logger.info(
            "Orchestrator finished tickers=%d duration_ms=%d providers_used=%s failures=%d mode=%s",
            len(watchlist), duration_ms,
            sorted(report.providers_used()), report.failure_count(),
            "parallel" if parallel else "sequential",
        )
        return collected, report

    def collect_ticker(
        self,
        item: WatchlistItem,
        run_date: date,
    ) -> tuple[CollectedTickerData, list[ProviderResult]]:
        """Public single-ticker entry point (thin wrapper for tests/external callers)."""
        return self._collect_for_ticker(item, run_date)

    # --------------------------- internals ---------------------------
    def _collect_for_ticker(
        self,
        item: WatchlistItem,
        run_date: date,
    ) -> tuple[CollectedTickerData, list[ProviderResult]]:
        """Run every applicable provider for one ticker and merge their output."""
        ctx = CollectionContext(
            watchlist_item=item,
            run_date=run_date,
            extra={
                "cache_get": self._cache.get if self._cache is not None else None,
                "cache_set": self._cache.set if self._cache is not None else None,
            },
        )
        merged_fields: dict[str, Any] = {}
        # Track which field came from which provider — enables priority-based override.
        field_origins: dict[str, int] = {}
        results: list[ProviderResult] = []

        # Iterate providers in global priority order for deterministic merging.
        providers = sorted(
            self._registry.all(),
            key=lambda p: (p.priority, p.name),
        )

        for provider in providers:
            if not self._provider_is_runnable(provider):
                results.append(
                    ProviderResult.skipped(provider.name, reason="not_available")
                )
                continue

            result = self._run_provider_with_cache(provider, item.ticker, ctx)
            results.append(result)

            if not result.ok or result.data is None:
                continue

            self._merge_into(
                merged_fields=merged_fields,
                field_origins=field_origins,
                incoming_provider=provider,
                incoming=result.data,
            )

        collected = self._build_collected(item, merged_fields)
        return collected, results

    def _provider_is_runnable(self, provider: DataProvider) -> bool:
        try:
            return provider.is_available()
        except Exception as err:  # noqa: BLE001
            logger.warning(
                "Provider %s is_available() raised: %s — skipping",
                provider.name, err,
            )
            return False

    def _run_provider_with_cache(
        self,
        provider: DataProvider,
        ticker: str,
        ctx: CollectionContext,
    ) -> ProviderResult:
        """Wrap provider.collect() with cache lookup, rate limiting, and error isolation."""
        cache_key = self._build_cache_key(provider, ticker, ctx.run_date)
        ttl_hours = self._resolve_ttl(provider)

        # 1. Cache lookup (fresh only on the happy path).
        if self._cache is not None and ttl_hours > 0:
            entry = self._cache.get(provider.name, cache_key)
            if entry is not None and not entry.is_stale:
                partial = _partial_from_payload(ticker, entry.payload)
                if partial is not None:
                    return ProviderResult.cached(provider.name, partial)

        # 2. Rate limit.
        self._rate_hub.acquire(provider.name)

        # 3. Execute provider.
        start = time.monotonic()
        try:
            result = provider.collect(ticker, ctx)
        except Exception as err:  # noqa: BLE001 — providers must not raise, but defend anyway.
            latency = int((time.monotonic() - start) * 1000)
            logger.exception(
                "Provider %s raised during collect(ticker=%s): %s",
                provider.name, ticker, err,
            )
            result = ProviderResult.failure(
                provider.name, reason=f"exception:{err}", latency_ms=latency,
            )

        # 4. Cache successful results.
        if result.ok and result.data is not None and self._cache is not None and ttl_hours > 0:
            self._cache.set(
                provider.name,
                cache_key,
                payload=dict(result.data.fields),
                ttl_hours=ttl_hours,
            )

        # 5. Stale fallback on live failure.
        if not result.ok and self._cache is not None:
            entry = self._cache.get(provider.name, cache_key)
            if entry is not None:
                partial = _partial_from_payload(ticker, entry.payload)
                if partial is not None:
                    logger.info(
                        "Provider %s failed for %s — serving stale cache (age=%.1fh)",
                        provider.name, ticker, entry.age_seconds / 3600,
                    )
                    return ProviderResult.cached(provider.name, partial)

        return result

    def _resolve_ttl(self, provider: DataProvider) -> float:
        """Maximum cache TTL among the data types this provider emits.

        We use the MAX so that a provider offering both `fundamentals`
        (24h) and `price` (0h) ends up with 24h — avoiding the churn of
        re-fetching fundamentals just because price is also in the mix.

        NOTE: this is a simplification. A more precise design would
        cache each data type independently. That optimization is
        deferred to Phase 1-3 when we split Polygon's options fields.
        """
        if not provider.provides:
            return 0.0
        return max(
            (self._cache_ttl.get(dt, 0.0) for dt in provider.provides),
            default=0.0,
        )

    @staticmethod
    def _build_cache_key(provider: DataProvider, ticker: str, run_date: date) -> str:
        return f"{ticker}:{run_date.isoformat()}"

    @staticmethod
    def _merge_into(
        merged_fields: dict[str, Any],
        field_origins: dict[str, int],
        incoming_provider: DataProvider,
        incoming: PartialTickerData,
    ) -> None:
        """Merge a provider's partial output into the aggregate.

        Rules:
          * Fields not yet set → always write.
          * Fields already set by a higher-priority provider → skip.
            (`higher priority` = lower priority number)
          * None / empty-string / 'N/A' incoming values → never overwrite
            a real value. This lets a lower-priority provider fill in
            gaps that the primary provider returned as 'N/A'.
        """
        incoming_priority = incoming_provider.priority
        for key, value in incoming.fields.items():
            if key == "options_summary" and isinstance(value, dict):
                existing_value = merged_fields.get(key)
                if isinstance(existing_value, dict):
                    merged_fields[key] = _merge_summary_dict(existing_value, value)
                    field_origins[key] = min(incoming_priority, field_origins.get(key, incoming_priority))
                    continue

            if value is None or value == "" or value == "N/A":
                # Don't let empty/placeholder values from a later provider
                # overwrite real data from an earlier one.
                if key not in merged_fields:
                    merged_fields[key] = value
                    field_origins[key] = incoming_priority
                continue

            existing_priority = field_origins.get(key)
            existing_value = merged_fields.get(key)
            # Upgrade a placeholder to real data, or prefer higher priority.
            if (
                existing_priority is None
                or existing_value in (None, "", "N/A")
                or incoming_priority < existing_priority
            ):
                merged_fields[key] = value
                field_origins[key] = incoming_priority

    @staticmethod
    def _build_collected(
        item: WatchlistItem,
        fields: dict[str, Any],
    ) -> CollectedTickerData:
        """Construct a CollectedTickerData with safe defaults for missing fields.

        The legacy `price.py` returns a CollectedTickerData with specific
        default string values (`'N/A'`) for missing fields. We preserve
        that convention so downstream code (analyzer, decision layer)
        doesn't have to distinguish None vs 'N/A'.
        """
        # Required positional-like fields with sane defaults.
        base = {
            "ticker": item.ticker,
            "name": fields.get("name", item.name),
            "sector": fields.get("sector", item.sector),
            "price": fields.get("price"),
            "change_percent": fields.get("change_percent"),
            "currency": fields.get("currency", "USD"),
            "market_cap": fields.get("market_cap", "N/A"),
            "pe_ratio": fields.get("pe_ratio", "N/A"),
            "summary_note": fields.get("summary_note", ""),
        }
        # Everything else passes through to the dataclass; CollectedTickerData
        # has defaults for all remaining fields.
        passthrough_keys = {
            f for f in fields
            if f not in base
        }
        kwargs: dict[str, Any] = dict(base)
        for k in passthrough_keys:
            kwargs[k] = fields[k]

        try:
            return CollectedTickerData(**kwargs)
        except TypeError as err:
            # Unknown keys (stale providers emitting fields we removed) — drop them.
            logger.warning(
                "CollectedTickerData init failed for %s: %s — dropping unknown fields",
                item.ticker, err,
            )
            known_fields = {
                name for name in CollectedTickerData.__dataclass_fields__  # type: ignore[attr-defined]
            }
            kwargs = {k: v for k, v in kwargs.items() if k in known_fields}
            return CollectedTickerData(**kwargs)


def _partial_from_payload(ticker: str, payload: Any) -> PartialTickerData | None:
    """Rehydrate a PartialTickerData from a cached JSON payload.

    Cached payloads are serialized dicts; lists/tuples/ints/strings/None.
    Returns None if the payload shape is unexpected (defensive).
    """
    if not isinstance(payload, dict):
        return None
    return PartialTickerData(ticker=ticker, fields=dict(payload))


def _merge_summary_dict(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged[key] in (None, "", "N/A"):
            merged[key] = value
    return merged


__all__ = [
    "CollectionOrchestrator",
    "OrchestrationReport",
    "DEFAULT_CACHE_TTL_HOURS",
]
