"""Unit tests for src/collector/orchestrator.py.

Covers the critical merge semantics that define multi-provider behaviour:
  * Higher-priority (lower number) wins when providers disagree
  * 'N/A' / None / '' never overwrite real data, regardless of priority
  * Lower-priority providers fill gaps left by higher-priority ones
  * Cache hits short-circuit live calls
  * Failures fall back to stale cache when available
  * Providers that raise don't crash the run
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.collector.cache import ResponseCache
from src.collector.orchestrator import (
    CollectionOrchestrator,
    OrchestrationReport,
)
from src.collector.rate_limiter import RateLimiterHub
from src.collector.registry import ProviderRegistry
from src.types import WatchlistItem


def _item(ticker: str = "AAPL") -> WatchlistItem:
    return WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", sector="Technology")


class _FakeProvider(DataProvider):
    """Test double: returns pre-baked fields deterministically."""

    def __init__(
        self,
        name: str,
        priority: int,
        fields: dict[str, object],
        *,
        available: bool = True,
        raises: bool = False,
        provides: set[str] | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self.provides = provides or {"price", "fundamentals"}
        self.rate_limit = RateLimit(calls_per_minute=6000, burst=10)  # effectively no throttle
        self._fields = fields
        self._available = available
        self._raises = raises
        self.call_count = 0

    def is_available(self) -> bool:
        return self._available

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        self.call_count += 1
        if self._raises:
            raise RuntimeError("provider exploded")
        return ProviderResult.success(
            self.name,
            PartialTickerData(ticker=ticker, fields=dict(self._fields)),
        )


class MergeSemanticsTests(unittest.TestCase):
    def _orchestrator(self, *providers: DataProvider) -> CollectionOrchestrator:
        reg = ProviderRegistry()
        for p in providers:
            reg.register(p)
        return CollectionOrchestrator(
            registry=reg,
            rate_hub=RateLimiterHub(),
            cache=None,
        )

    def test_higher_priority_wins(self) -> None:
        primary = _FakeProvider("primary", priority=1, fields={"price": 100.0})
        fallback = _FakeProvider("fallback", priority=3, fields={"price": 99.0})
        orch = self._orchestrator(primary, fallback)
        collected, _ = orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(collected["AAPL"].price, 100.0)

    def test_fallback_fills_gap(self) -> None:
        primary = _FakeProvider("primary", priority=1, fields={"price": 100.0, "market_cap": "N/A"})
        fallback = _FakeProvider("fallback", priority=3, fields={"market_cap": "2T"})
        orch = self._orchestrator(primary, fallback)
        collected, _ = orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(collected["AAPL"].price, 100.0)
        self.assertEqual(collected["AAPL"].market_cap, "2T")

    def test_na_never_overwrites_real_value(self) -> None:
        primary = _FakeProvider("primary", priority=1, fields={"pe_ratio": "25.3"})
        fallback = _FakeProvider("fallback", priority=3, fields={"pe_ratio": "N/A"})
        orch = self._orchestrator(primary, fallback)
        collected, _ = orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(collected["AAPL"].pe_ratio, "25.3")

    def test_unavailable_provider_skipped(self) -> None:
        off = _FakeProvider("off", priority=1, fields={"price": 1.0}, available=False)
        on = _FakeProvider("on", priority=2, fields={"price": 2.0})
        orch = self._orchestrator(off, on)
        collected, report = orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(collected["AAPL"].price, 2.0)
        self.assertEqual(off.call_count, 0)
        self.assertIn("on", report.providers_used())

    def test_exception_isolated_to_provider(self) -> None:
        boom = _FakeProvider("boom", priority=1, fields={}, raises=True)
        ok = _FakeProvider("ok", priority=2, fields={"price": 42.0})
        orch = self._orchestrator(boom, ok)
        collected, report = orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(collected["AAPL"].price, 42.0)
        self.assertEqual(report.failure_count(), 1)


class CacheIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._cache = ResponseCache(Path(self._tmp.name) / "cache.sqlite")

    def tearDown(self) -> None:
        self._cache.close()
        self._tmp.cleanup()

    def _orchestrator(self, *providers: DataProvider) -> CollectionOrchestrator:
        reg = ProviderRegistry()
        for p in providers:
            reg.register(p)
        return CollectionOrchestrator(
            registry=reg,
            rate_hub=RateLimiterHub(),
            cache=self._cache,
            cache_ttl_hours={"fundamentals": 24.0},
        )

    def test_cache_hit_skips_live_call(self) -> None:
        provider = _FakeProvider(
            "yfinance", priority=1,
            fields={"market_cap": "3T"},
            provides={"fundamentals"},
        )
        orch = self._orchestrator(provider)
        # First run populates cache.
        orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(provider.call_count, 1)
        # Second run should hit the cache, leaving call_count unchanged.
        orch.collect_all([_item()], date(2026, 4, 15))
        self.assertEqual(provider.call_count, 1)

    def test_failure_falls_back_to_stale_cache(self) -> None:
        # First run: provider succeeds → writes cache.
        good = _FakeProvider(
            "yfinance", priority=1,
            fields={"market_cap": "3T"},
            provides={"fundamentals"},
        )
        orch = self._orchestrator(good)
        orch.collect_all([_item()], date(2026, 4, 15))

        # Second run: same provider now fails → stale cache served.
        bad = _FakeProvider(
            "yfinance", priority=1,
            fields={},
            provides={"fundamentals"},
            raises=True,
        )
        orch_fail = self._orchestrator(bad)
        # Run next day so the cache-key differs unless we reuse date.
        collected, report = orch_fail.collect_all([_item()], date(2026, 4, 15))
        # Stale fallback kicks in → market_cap preserved from prior run.
        self.assertEqual(collected["AAPL"].market_cap, "3T")
        self.assertIn("yfinance", report.providers_used())


class OrchestrationReportTests(unittest.TestCase):
    def test_providers_used_only_counts_success_and_cache(self) -> None:
        report = OrchestrationReport(
            results_by_ticker={
                "AAPL": [
                    ProviderResult.success("yf", PartialTickerData(ticker="AAPL", fields={})),
                    ProviderResult.failure("fmp", reason="429"),
                    ProviderResult.skipped("polygon", reason="api_key"),
                ],
            },
        )
        self.assertEqual(report.providers_used(), {"yf"})
        self.assertEqual(report.failure_count(), 1)


# ---------------------------------------------------------------------------
# Phase 1-1: parallel ticker collection
# ---------------------------------------------------------------------------
class _SlowProvider(DataProvider):
    """Sleeps for a fixed duration on every collect() — lets us measure
    whether tickers ran concurrently (wall time) vs sequentially.
    """

    def __init__(self, name: str, priority: int, sleep_seconds: float) -> None:
        self.name = name
        self.priority = priority
        self.provides = {"price"}
        self.rate_limit = RateLimit(calls_per_minute=6000, burst=100)
        self._sleep = sleep_seconds
        self._lock = __import__("threading").Lock()
        self.threads_seen: set[str] = set()

    def is_available(self) -> bool:
        return True

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        import threading
        import time as _time
        with self._lock:
            self.threads_seen.add(threading.current_thread().name)
        _time.sleep(self._sleep)
        return ProviderResult.success(
            self.name,
            PartialTickerData(ticker=ticker, fields={"price": 100.0}),
        )


class ParallelCollectionTests(unittest.TestCase):
    def _orchestrator(self, provider: DataProvider, max_workers: int | None) -> CollectionOrchestrator:
        reg = ProviderRegistry()
        reg.register(provider)
        return CollectionOrchestrator(
            registry=reg,
            rate_hub=RateLimiterHub(),
            cache=None,
            max_workers=max_workers,
        )

    def test_max_workers_below_one_rejected(self) -> None:
        reg = ProviderRegistry()
        with self.assertRaises(ValueError):
            CollectionOrchestrator(registry=reg, max_workers=0)
        with self.assertRaises(ValueError):
            CollectionOrchestrator(registry=reg, max_workers=-5)

    def test_sequential_mode_when_workers_none(self) -> None:
        """max_workers=None → legacy sequential path, one thread only."""
        provider = _SlowProvider("slow", priority=1, sleep_seconds=0.05)
        orch = self._orchestrator(provider, max_workers=None)
        watchlist = [_item("AAPL"), _item("MSFT"), _item("GOOG"), _item("TSLA")]
        collected, _ = orch.collect_all(watchlist, date(2026, 4, 15))

        self.assertEqual(len(collected), 4)
        # Sequential path uses the main thread, so exactly 1 worker seen.
        self.assertEqual(len(provider.threads_seen), 1)

    def test_parallel_mode_uses_multiple_threads(self) -> None:
        provider = _SlowProvider("slow", priority=1, sleep_seconds=0.05)
        orch = self._orchestrator(provider, max_workers=4)
        watchlist = [_item("AAPL"), _item("MSFT"), _item("GOOG"), _item("TSLA")]
        collected, _ = orch.collect_all(watchlist, date(2026, 4, 15))

        self.assertEqual(len(collected), 4)
        # At least 2 different worker threads should have executed collect().
        # Can't assert ==4 because the pool may reuse threads when tasks
        # finish out of order.
        self.assertGreaterEqual(len(provider.threads_seen), 2)

    def test_parallel_faster_than_sequential(self) -> None:
        """Wall-clock sanity check: 4 tickers × 0.1s should beat sequential."""
        import time as _time

        def run_with(workers: int | None) -> float:
            provider = _SlowProvider("slow", priority=1, sleep_seconds=0.1)
            orch = self._orchestrator(provider, max_workers=workers)
            watchlist = [_item(f"T{i}") for i in range(4)]
            start = _time.monotonic()
            orch.collect_all(watchlist, date(2026, 4, 15))
            return _time.monotonic() - start

        seq_time = run_with(None)
        par_time = run_with(4)
        # Sequential: ~0.4s. Parallel with 4 workers: ~0.1s + overhead.
        # Use a generous threshold to avoid flakes on slow CI.
        self.assertLess(par_time, seq_time * 0.75)

    def test_single_ticker_skips_thread_pool(self) -> None:
        """Pointless to spin up a pool for one ticker — stays sequential."""
        provider = _SlowProvider("slow", priority=1, sleep_seconds=0.01)
        orch = self._orchestrator(provider, max_workers=4)
        orch.collect_all([_item()], date(2026, 4, 15))
        # Only main thread should have executed collect().
        self.assertEqual(len(provider.threads_seen), 1)

    def test_parallel_preserves_all_results(self) -> None:
        """Every ticker must appear in the output, regardless of scheduling order."""
        provider = _FakeProvider("fast", priority=1, fields={"price": 42.0})
        orch = self._orchestrator(provider, max_workers=3)
        tickers = [f"TICK{i}" for i in range(10)]
        watchlist = [_item(t) for t in tickers]
        collected, report = orch.collect_all(watchlist, date(2026, 4, 15))

        self.assertEqual(set(collected.keys()), set(tickers))
        for t in tickers:
            self.assertEqual(collected[t].price, 42.0)
        self.assertEqual(len(report.results_by_ticker), 10)

    def test_parallel_isolates_exceptions_per_ticker(self) -> None:
        """A provider blowing up for one ticker shouldn't kill the run."""
        # _FakeProvider with raises=True raises for EVERY ticker — use a
        # conditional provider instead.
        class _ConditionalBoom(DataProvider):
            name = "boom"
            priority = 1
            provides = {"price"}
            rate_limit = RateLimit(calls_per_minute=6000, burst=100)

            def is_available(self) -> bool:
                return True

            def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
                if ticker == "BAD":
                    raise RuntimeError("simulated failure")
                return ProviderResult.success(
                    self.name,
                    PartialTickerData(ticker=ticker, fields={"price": 1.0}),
                )

        orch = self._orchestrator(_ConditionalBoom(), max_workers=3)
        watchlist = [_item("GOOD1"), _item("BAD"), _item("GOOD2")]
        collected, report = orch.collect_all(watchlist, date(2026, 4, 15))

        # BAD ticker returns a failure ProviderResult (exception caught in
        # _run_provider_with_cache) but the ticker itself is still present
        # with default fields because _collect_for_ticker never raises.
        self.assertIn("GOOD1", collected)
        self.assertIn("GOOD2", collected)
        self.assertIn("BAD", collected)
        self.assertEqual(collected["GOOD1"].price, 1.0)
        self.assertIsNone(collected["BAD"].price)
        self.assertEqual(report.failure_count(), 1)


class ResolveMaxWorkersTests(unittest.TestCase):
    """Covers the env-var resolution helper in orchestrated_collection."""

    def _reimport(self):
        from src.collector import orchestrated_collection
        return orchestrated_collection

    def test_explicit_override_wins(self) -> None:
        oc = self._reimport()
        self.assertEqual(oc._resolve_max_workers(7), 7)

    def test_override_clamped_to_minimum_one(self) -> None:
        oc = self._reimport()
        self.assertEqual(oc._resolve_max_workers(0), 1)
        self.assertEqual(oc._resolve_max_workers(-3), 1)

    def test_env_var_parsed(self) -> None:
        import os
        oc = self._reimport()
        prev = os.environ.get("COLLECTOR_MAX_WORKERS")
        try:
            os.environ["COLLECTOR_MAX_WORKERS"] = "8"
            self.assertEqual(oc._resolve_max_workers(None), 8)
        finally:
            if prev is None:
                os.environ.pop("COLLECTOR_MAX_WORKERS", None)
            else:
                os.environ["COLLECTOR_MAX_WORKERS"] = prev

    def test_invalid_env_var_falls_back_to_default(self) -> None:
        import os
        oc = self._reimport()
        prev = os.environ.get("COLLECTOR_MAX_WORKERS")
        try:
            os.environ["COLLECTOR_MAX_WORKERS"] = "not-a-number"
            self.assertEqual(oc._resolve_max_workers(None), oc._DEFAULT_MAX_WORKERS)
            os.environ["COLLECTOR_MAX_WORKERS"] = "0"
            self.assertEqual(oc._resolve_max_workers(None), oc._DEFAULT_MAX_WORKERS)
        finally:
            if prev is None:
                os.environ.pop("COLLECTOR_MAX_WORKERS", None)
            else:
                os.environ["COLLECTOR_MAX_WORKERS"] = prev

    def test_missing_env_var_uses_default(self) -> None:
        import os
        oc = self._reimport()
        prev = os.environ.pop("COLLECTOR_MAX_WORKERS", None)
        try:
            self.assertEqual(oc._resolve_max_workers(None), oc._DEFAULT_MAX_WORKERS)
        finally:
            if prev is not None:
                os.environ["COLLECTOR_MAX_WORKERS"] = prev


if __name__ == "__main__":
    unittest.main()
