"""Unit tests for src/collector/news_base.py.

Thin layer: the base is just dataclasses + an ABC. The tests check factory
invariants (success/failure/skipped) and that the ABC refuses instantiation
without both methods. Regression insurance if someone refactors the types.
"""
from __future__ import annotations

import unittest
from datetime import date

from src.collector.news_base import NewsContext, NewsProvider, NewsResult
from src.types import NewsItem, WatchlistItem


def _make_item(title: str = "Earnings beat") -> NewsItem:
    return NewsItem(title=title, source="Reuters", published_at="", link="https://x")


class NewsResultTests(unittest.TestCase):
    def test_success_marks_ok_and_carries_items(self) -> None:
        items = [_make_item("a"), _make_item("b")]
        result = NewsResult.success("sec_edgar", items=items, latency_ms=120)
        self.assertEqual(result.status, "success")
        self.assertTrue(result.ok)
        self.assertEqual(result.items, items)
        self.assertEqual(result.provider, "sec_edgar")
        self.assertEqual(result.latency_ms, 120)
        self.assertEqual(result.reason, "")

    def test_failure_is_not_ok_and_carries_reason(self) -> None:
        result = NewsResult.failure("ir_rss", reason="network_down", latency_ms=5)
        self.assertEqual(result.status, "failure")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "network_down")
        self.assertEqual(result.items, [])

    def test_skipped_is_not_ok(self) -> None:
        result = NewsResult.skipped("sec_edgar", reason="missing_cik")
        self.assertEqual(result.status, "skipped")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "missing_cik")
        self.assertEqual(result.items, [])

    def test_result_is_frozen(self) -> None:
        # Frozen dataclass — assigning any field should raise.
        result = NewsResult.success("x", items=[])
        with self.assertRaises(Exception):
            result.provider = "y"  # type: ignore[misc]


class NewsContextTests(unittest.TestCase):
    def test_defaults_and_field_access(self) -> None:
        item = WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Tech")
        ctx = NewsContext(watchlist_item=item, run_date=date(2026, 4, 15))
        self.assertEqual(ctx.watchlist_item.ticker, "AAPL")
        self.assertEqual(ctx.run_date, date(2026, 4, 15))
        self.assertEqual(ctx.extra, {})

    def test_extra_can_carry_cross_provider_hints(self) -> None:
        item = WatchlistItem(ticker="AAPL", name="Apple")
        ctx = NewsContext(
            watchlist_item=item,
            run_date=date(2026, 4, 15),
            extra={"sec_edgar_available": True},
        )
        self.assertTrue(ctx.extra["sec_edgar_available"])


class NewsProviderABCTests(unittest.TestCase):
    def test_missing_methods_cannot_instantiate(self) -> None:
        class PartialProvider(NewsProvider):
            name = "x"

            def is_available(self, ctx: NewsContext) -> bool:  # no collect
                return True

        with self.assertRaises(TypeError):
            PartialProvider()  # type: ignore[abstract]

    def test_complete_subclass_instantiates(self) -> None:
        class CompleteProvider(NewsProvider):
            name = "ok"
            source_priority = 3

            def is_available(self, ctx: NewsContext) -> bool:
                return True

            def collect(self, ctx: NewsContext) -> NewsResult:
                return NewsResult.success(self.name, items=[])

        provider = CompleteProvider()
        self.assertEqual(provider.name, "ok")
        self.assertEqual(provider.source_priority, 3)


if __name__ == "__main__":
    unittest.main()
