"""Unit tests for src/collector/news_orchestrator.py.

Covers the pieces that matter most when Step 5 cutover happens:
  * register / collect_all happy + mixed-status path
  * dedup keeps the higher-priority copy
  * ranking puts higher source_priority first, then fresher
  * exclude_keywords filter removes offending items
  * truncation respects max_items_per_ticker
  * age parsing handles RFC 2822 + ISO 8601 + junk
  * defensive handling when a provider's is_available / collect raises

Keeping these as plain unittest (not pytest) to match the rest of the suite.
"""
from __future__ import annotations

import unittest
from datetime import date
from typing import Iterable

from src.collector.base import RateLimit
from src.collector.news_base import NewsContext, NewsProvider, NewsResult
from src.collector.news_orchestrator import (
    NewsOrchestrator,
    _age_in_days,
    _dedup_by_title,
    _matches_excluded,
    _normalize_title,
    _rank_key,
)
from src.types import NewsItem, WatchlistItem


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeProvider(NewsProvider):
    """Test double configurable via constructor args."""

    def __init__(
        self,
        *,
        name: str,
        source_priority: int = 1,
        items: Iterable[NewsItem] = (),
        available: bool = True,
        fail_with: str | None = None,
        skip_reason: str | None = None,
        raise_in_collect: bool = False,
        raise_in_available: bool = False,
    ) -> None:
        self.name = name
        self.source_priority = source_priority
        self.rate_limit = RateLimit(calls_per_minute=1000, burst=100)
        self._items = list(items)
        self._available = available
        self._fail_with = fail_with
        self._skip_reason = skip_reason
        self._raise_in_collect = raise_in_collect
        self._raise_in_available = raise_in_available

    def is_available(self, ctx: NewsContext) -> bool:  # pragma: no cover — trivial
        if self._raise_in_available:
            raise RuntimeError("boom-available")
        return self._available

    def collect(self, ctx: NewsContext) -> NewsResult:
        if self._raise_in_collect:
            raise RuntimeError("boom-collect")
        if self._skip_reason:
            return NewsResult.skipped(self.name, reason=self._skip_reason)
        if self._fail_with:
            return NewsResult.failure(self.name, reason=self._fail_with)
        return NewsResult.success(self.name, items=list(self._items))


def _wl(ticker: str = "AAPL", **overrides: object) -> WatchlistItem:
    return WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", **overrides)  # type: ignore[arg-type]


def _item(title: str, source: str = "Reuters", published_at: str = "") -> NewsItem:
    return NewsItem(title=title, source=source, published_at=published_at, link=f"https://x/{title}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class NewsOrchestratorRegistrationTests(unittest.TestCase):
    def test_register_rejects_nameless_provider(self) -> None:
        orch = NewsOrchestrator()
        nameless = _FakeProvider(name="")
        with self.assertRaises(ValueError):
            orch.register(nameless)

    def test_register_all_adds_each(self) -> None:
        orch = NewsOrchestrator()
        a = _FakeProvider(name="a")
        b = _FakeProvider(name="b")
        orch.register_all([a, b])
        names = [p.name for p in orch.providers]
        self.assertEqual(names, ["a", "b"])

    def test_providers_returns_a_copy(self) -> None:
        orch = NewsOrchestrator()
        orch.register(_FakeProvider(name="a"))
        snapshot = orch.providers
        snapshot.append(_FakeProvider(name="mutant"))
        # Original list must not be mutated.
        self.assertEqual([p.name for p in orch.providers], ["a"])


# ---------------------------------------------------------------------------
# collect_all integration
# ---------------------------------------------------------------------------
class NewsOrchestratorCollectAllTests(unittest.TestCase):
    def test_happy_path_merges_across_providers(self) -> None:
        # SEC item and Reuters item — both survive, both distinct titles.
        a = _FakeProvider(
            name="sec_edgar",
            source_priority=4,
            items=[_item("Apple files 8-K", source="SEC EDGAR")],
        )
        b = _FakeProvider(
            name="ir_rss",
            source_priority=2,
            items=[_item("Apple announces new product", source="Apple Newsroom")],
        )
        orch = NewsOrchestrator(max_items_per_ticker=10)
        orch.register_all([a, b])

        per_ticker, report = orch.collect_all([_wl("AAPL")], date(2026, 4, 15))
        self.assertEqual(len(per_ticker["AAPL"]), 2)
        self.assertEqual(report.per_provider_counts, {"sec_edgar": 1, "ir_rss": 1})
        self.assertEqual(report.per_ticker_counts, {"AAPL": 2})
        self.assertEqual(report.provider_failures, [])

    def test_failure_records_without_dropping_other_providers(self) -> None:
        a = _FakeProvider(name="sec_edgar", source_priority=4, fail_with="http_500")
        b = _FakeProvider(
            name="ir_rss",
            source_priority=2,
            items=[_item("IR news")],
        )
        orch = NewsOrchestrator()
        orch.register_all([a, b])

        per_ticker, report = orch.collect_all([_wl()], date(2026, 4, 15))
        self.assertEqual(len(per_ticker["AAPL"]), 1)
        self.assertEqual(report.per_provider_counts, {"ir_rss": 1})
        self.assertEqual(
            report.provider_failures, [("sec_edgar", "AAPL", "http_500")]
        )

    def test_skipped_status_is_not_a_failure(self) -> None:
        a = _FakeProvider(name="sec_edgar", skip_reason="missing_cik")
        orch = NewsOrchestrator()
        orch.register(a)

        per_ticker, report = orch.collect_all([_wl()], date(2026, 4, 15))
        self.assertEqual(per_ticker["AAPL"], [])
        self.assertEqual(report.provider_failures, [])
        self.assertEqual(report.per_provider_counts, {})

    def test_is_available_false_never_calls_collect(self) -> None:
        a = _FakeProvider(name="sec_edgar", available=False, items=[_item("x")])
        orch = NewsOrchestrator()
        orch.register(a)

        per_ticker, report = orch.collect_all([_wl()], date(2026, 4, 15))
        self.assertEqual(per_ticker["AAPL"], [])
        self.assertEqual(report.per_provider_counts, {})
        self.assertEqual(report.provider_failures, [])

    def test_exception_in_collect_is_caught(self) -> None:
        a = _FakeProvider(name="sec_edgar", raise_in_collect=True)
        b = _FakeProvider(name="ir_rss", items=[_item("kept")])
        orch = NewsOrchestrator()
        orch.register_all([a, b])

        per_ticker, report = orch.collect_all([_wl()], date(2026, 4, 15))
        self.assertEqual(len(per_ticker["AAPL"]), 1)
        self.assertEqual(len(report.provider_failures), 1)
        failed_name, failed_ticker, reason = report.provider_failures[0]
        self.assertEqual(failed_name, "sec_edgar")
        self.assertEqual(failed_ticker, "AAPL")
        self.assertIn("boom-collect", reason)

    def test_exception_in_is_available_is_caught(self) -> None:
        a = _FakeProvider(name="sec_edgar", raise_in_available=True)
        b = _FakeProvider(name="ir_rss", items=[_item("kept")])
        orch = NewsOrchestrator()
        orch.register_all([a, b])

        per_ticker, report = orch.collect_all([_wl()], date(2026, 4, 15))
        self.assertEqual(len(per_ticker["AAPL"]), 1)
        self.assertEqual(
            [name for name, *_ in report.provider_failures], ["sec_edgar"]
        )


# ---------------------------------------------------------------------------
# Merge / dedup / rank / truncate
# ---------------------------------------------------------------------------
class NewsOrchestratorMergeTests(unittest.TestCase):
    def test_dedup_keeps_higher_source_priority(self) -> None:
        # Same headline reached us from a cheap aggregator (priority 1)
        # and from SEC EDGAR (priority 4). Keep the SEC copy.
        low = _FakeProvider(
            name="aggregator",
            source_priority=1,
            items=[_item("Apple reports Q4 earnings", source="Blog")],
        )
        high = _FakeProvider(
            name="sec_edgar",
            source_priority=4,
            items=[_item("Apple reports Q4 earnings", source="SEC EDGAR")],
        )
        orch = NewsOrchestrator()
        orch.register_all([low, high])

        per_ticker, _ = orch.collect_all([_wl()], date(2026, 4, 15))
        kept = per_ticker["AAPL"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].source, "SEC EDGAR")

    def test_exclude_keywords_drops_matching_items(self) -> None:
        items = [
            _item("Apple CEO rumor speculation"),
            _item("Apple Q4 earnings beat"),
        ]
        prov = _FakeProvider(name="ir_rss", items=items)
        orch = NewsOrchestrator()
        orch.register(prov)

        wl = _wl("AAPL", exclude_keywords=["rumor"])
        per_ticker, _ = orch.collect_all([wl], date(2026, 4, 15))
        titles = [it.title for it in per_ticker["AAPL"]]
        self.assertEqual(titles, ["Apple Q4 earnings beat"])

    def test_ranking_higher_priority_beats_lower(self) -> None:
        older_sec = _item(
            "SEC filing",
            source="SEC EDGAR",
            published_at="Mon, 01 Apr 2026 10:00:00 GMT",
        )
        newer_blog = _item(
            "Blog post",
            source="Blog",
            published_at="Tue, 14 Apr 2026 10:00:00 GMT",
        )
        high = _FakeProvider(name="sec_edgar", source_priority=4, items=[older_sec])
        low = _FakeProvider(name="blog", source_priority=1, items=[newer_blog])

        orch = NewsOrchestrator()
        orch.register_all([high, low])

        per_ticker, _ = orch.collect_all([_wl()], date(2026, 4, 15))
        # Priority tier dominates over freshness.
        self.assertEqual(per_ticker["AAPL"][0].title, "SEC filing")

    def test_truncation_respects_max_items(self) -> None:
        items = [_item(f"headline {i}") for i in range(20)]
        prov = _FakeProvider(name="agg", items=items)
        orch = NewsOrchestrator(max_items_per_ticker=3)
        orch.register(prov)

        per_ticker, _ = orch.collect_all([_wl()], date(2026, 4, 15))
        self.assertEqual(len(per_ticker["AAPL"]), 3)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
class PureHelperTests(unittest.TestCase):
    def test_normalize_title_collapses_whitespace_and_lowercases(self) -> None:
        self.assertEqual(
            _normalize_title("  Apple  reports\tQ4  EARNINGS  "),
            "apple reports q4 earnings",
        )

    def test_matches_excluded_handles_empty_list(self) -> None:
        item = _item("Apple rumor")
        self.assertFalse(_matches_excluded(item, []))
        self.assertTrue(_matches_excluded(item, ["RUMOR"]))  # case-insensitive
        self.assertFalse(_matches_excluded(item, [""]))  # empty string ignored

    def test_dedup_by_title_skips_empty_titles(self) -> None:
        with_priority = [
            (_item(""), 5),  # empty-title — skipped entirely
            (_item("Real headline"), 2),
        ]
        out = _dedup_by_title(with_priority)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0].title, "Real headline")

    def test_age_in_days_rfc2822(self) -> None:
        days = _age_in_days("Mon, 01 Apr 2026 12:00:00 GMT", date(2026, 4, 15))
        assert days is not None
        self.assertAlmostEqual(days, 13.5, places=1)

    def test_age_in_days_iso_8601_with_z(self) -> None:
        days = _age_in_days("2026-04-10T12:00:00Z", date(2026, 4, 15))
        assert days is not None
        self.assertAlmostEqual(days, 4.5, places=1)

    def test_age_in_days_junk_returns_none(self) -> None:
        self.assertIsNone(_age_in_days("not a date", date(2026, 4, 15)))
        self.assertIsNone(_age_in_days("", date(2026, 4, 15)))

    def test_rank_key_orders_by_priority_then_freshness_then_catalyst(self) -> None:
        run = date(2026, 4, 15)
        fresh_earnings = _item(
            "Apple earnings beat",
            source="Reuters",
            published_at="Tue, 14 Apr 2026 12:00:00 GMT",
        )
        stale_unrelated = _item(
            "Apple style news",
            source="Blog",
            published_at="Tue, 14 Apr 2026 12:00:00 GMT",
        )
        # Same priority, same date → catalyst tiebreak favors earnings.
        key_fresh = _rank_key(fresh_earnings, 2, run)
        key_stale = _rank_key(stale_unrelated, 2, run)
        self.assertGreater(key_fresh, key_stale)


if __name__ == "__main__":
    unittest.main()
