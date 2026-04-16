"""Unit tests for src/collector/base.py core contracts."""
from __future__ import annotations

import unittest
from datetime import date

from src.collector.base import (
    DATA_TYPES,
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.types import WatchlistItem


def _make_item(ticker: str = "AAPL") -> WatchlistItem:
    return WatchlistItem(ticker=ticker, name="Apple Inc.", sector="Technology")


class RateLimitTests(unittest.TestCase):
    def test_effective_burst_defaults_to_cpm_when_burst_missing(self) -> None:
        rl = RateLimit(calls_per_minute=60)
        self.assertEqual(rl.effective_burst, 60)

    def test_effective_burst_uses_explicit_value(self) -> None:
        rl = RateLimit(calls_per_minute=60, burst=10)
        self.assertEqual(rl.effective_burst, 10)


class PartialTickerDataTests(unittest.TestCase):
    def test_has_true_when_field_set(self) -> None:
        p = PartialTickerData(ticker="AAPL", fields={"price": 100.0})
        self.assertTrue(p.has("price"))

    def test_has_false_when_field_none(self) -> None:
        p = PartialTickerData(ticker="AAPL", fields={"price": None})
        self.assertFalse(p.has("price"))

    def test_has_false_when_field_absent(self) -> None:
        p = PartialTickerData(ticker="AAPL", fields={})
        self.assertFalse(p.has("price"))


class ProviderResultTests(unittest.TestCase):
    def test_success_factory(self) -> None:
        payload = PartialTickerData(ticker="AAPL", fields={"price": 100})
        r = ProviderResult.success("yfinance", payload, latency_ms=42)
        self.assertEqual(r.status, "success")
        self.assertTrue(r.ok)
        self.assertIs(r.data, payload)
        self.assertEqual(r.latency_ms, 42)

    def test_failure_factory_has_no_data(self) -> None:
        r = ProviderResult.failure("yfinance", reason="timeout")
        self.assertEqual(r.status, "failure")
        self.assertFalse(r.ok)
        self.assertIsNone(r.data)
        self.assertEqual(r.reason, "timeout")

    def test_skipped_is_not_ok(self) -> None:
        r = ProviderResult.skipped("fmp", reason="api_key_missing")
        self.assertFalse(r.ok)

    def test_cached_counts_as_ok(self) -> None:
        payload = PartialTickerData(ticker="AAPL", fields={})
        r = ProviderResult.cached("yfinance", payload)
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "cached")


class DataTypeTaxonomyTests(unittest.TestCase):
    def test_core_types_present(self) -> None:
        for expected in {"price", "fundamentals", "news", "sec_filings"}:
            self.assertIn(expected, DATA_TYPES)


class DataProviderContractTests(unittest.TestCase):
    def test_abstract_methods_required(self) -> None:
        """Subclasses must implement is_available() and collect()."""
        with self.assertRaises(TypeError):
            DataProvider()  # type: ignore[abstract]

    def test_minimal_subclass_instantiates(self) -> None:
        class Dummy(DataProvider):
            name = "dummy"
            provides = {"price"}
            priority = 5

            def is_available(self) -> bool:
                return True

            def collect(self, ticker, ctx):
                return ProviderResult.success(
                    self.name,
                    PartialTickerData(ticker=ticker, fields={"price": 42}),
                )

        d = Dummy()
        self.assertTrue(d.is_available())
        ctx = CollectionContext(watchlist_item=_make_item(), run_date=date(2026, 4, 15))
        result = d.collect("AAPL", ctx)
        self.assertTrue(result.ok)
        self.assertEqual(result.data.fields["price"], 42)


if __name__ == "__main__":
    unittest.main()
