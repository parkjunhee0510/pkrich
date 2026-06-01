"""Unit tests for src/collector/providers/news/google_news_news_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.collector.news_base import NewsContext
from src.collector.providers.news.google_news_news_provider import (
    GoogleNewsNewsProvider,
    _build_query,
)
from src.collector.news_title_utils import looks_like_unresolved_placeholder
from src.types import WatchlistItem


def _ctx(*, extra: dict[str, object] | None = None) -> NewsContext:
    item = WatchlistItem(
        ticker="AAPL",
        name="Apple Inc.",
        keywords=["iphone", "services"],
    )
    return NewsContext(watchlist_item=item, run_date=date(2026, 4, 15), extra=extra or {})


class GoogleNewsMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = GoogleNewsNewsProvider()
        self.assertEqual(p.name, "google_news")
        self.assertEqual(p.source_priority, 1)


class GoogleNewsIsAvailableTests(unittest.TestCase):
    def test_returns_false_when_env_flag_disabled(self) -> None:
        p = GoogleNewsNewsProvider()
        with patch(
            "src.collector.providers.news.google_news_news_provider.is_env_flag_enabled",
            return_value=False,
        ):
            self.assertFalse(p.is_available(_ctx()))

    def test_honors_extra_cache_true(self) -> None:
        p = GoogleNewsNewsProvider()
        with patch(
            "src.collector.providers.news.google_news_news_provider.can_open_tcp_connection",
        ) as probe:
            self.assertTrue(
                p.is_available(_ctx(extra={"google_news_available": True}))
            )
            probe.assert_not_called()

    def test_honors_extra_cache_false(self) -> None:
        p = GoogleNewsNewsProvider()
        with patch(
            "src.collector.providers.news.google_news_news_provider.can_open_tcp_connection",
        ) as probe:
            self.assertFalse(
                p.is_available(_ctx(extra={"google_news_available": False}))
            )
            probe.assert_not_called()

    def test_falls_back_to_tcp_probe(self) -> None:
        p = GoogleNewsNewsProvider()
        with patch(
            "src.collector.providers.news.google_news_news_provider.can_open_tcp_connection",
            return_value=True,
        ):
            self.assertTrue(p.is_available(_ctx()))

    def test_probe_exception_returns_false(self) -> None:
        p = GoogleNewsNewsProvider()
        with patch(
            "src.collector.providers.news.google_news_news_provider.can_open_tcp_connection",
            side_effect=OSError("refused"),
        ):
            self.assertFalse(p.is_available(_ctx()))


class GoogleNewsCollectTests(unittest.TestCase):
    def _build_feed(self, titles: list[str]) -> SimpleNamespace:
        entries = [
            SimpleNamespace(
                title=title,
                published="Mon, 14 Apr 2026 10:00:00 GMT",
                link=f"https://news.google.com/{title}",
                source={"title": "Reuters"},  # override outlet
            )
            for title in titles
        ]
        return SimpleNamespace(entries=entries)

    def test_collect_iterates_all_feeds(self) -> None:
        """Happy path: feedparser.parse() is called once per feed (6 feeds)."""
        fake = MagicMock()
        fake.parse.return_value = self._build_feed(["A", "B"])
        p = GoogleNewsNewsProvider()

        with patch("src.collector.providers.news.google_news_news_provider.parse_feed", fake.parse):
            result = p.collect(_ctx())

        self.assertEqual(result.status, "success")
        # 6 feeds × 2 entries each = 12 items.
        self.assertEqual(len(result.items), 12)
        # All items carry the overridden Reuters source.
        self.assertTrue(all(item.source == "Reuters" for item in result.items))
        self.assertEqual(fake.parse.call_count, 6)

    def test_collect_skips_empty_titles(self) -> None:
        fake = MagicMock()
        # One feed returns items with empty titles — should be dropped.
        entries = [
            SimpleNamespace(title="", published="", link="", source=None),
            SimpleNamespace(title="Real headline", published="", link="https://x", source=None),
        ]
        fake.parse.return_value = SimpleNamespace(entries=entries)
        p = GoogleNewsNewsProvider()

        with patch("src.collector.providers.news.google_news_news_provider.parse_feed", fake.parse):
            result = p.collect(_ctx())

        # 6 feeds × 1 valid entry each = 6 items.
        self.assertEqual(len(result.items), 6)
        self.assertTrue(all(item.title == "Real headline" for item in result.items))

    def test_collect_returns_failure_when_feedparser_missing(self) -> None:
        p = GoogleNewsNewsProvider()
        # Simulate ImportError by making feedparser import raise inside collect.
        with patch.dict("sys.modules", {"feedparser": None}):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("feedparser_missing", result.reason)

    def test_collect_drops_placeholder_titles(self) -> None:
        fake = MagicMock()
        fake.parse.return_value = self._build_feed(
            ["META_TITLE_QUOTE - Yahoo Finance", "Meta_Title_Quote - Yahoo Finance", "Real headline"]
        )
        p = GoogleNewsNewsProvider()

        with patch("src.collector.providers.news.google_news_news_provider.parse_feed", fake.parse):
            result = p.collect(_ctx())

        self.assertEqual(len(result.items), 6)
        self.assertTrue(all(item.title == "Real headline" for item in result.items))

    def test_single_feed_failure_does_not_kill_others(self) -> None:
        """If one of the 6 feed parses raises, others still contribute items."""
        fake = MagicMock()
        call_count = {"n": 0}

        def side_effect(url: str) -> SimpleNamespace:  # noqa: ARG001
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("feed 2 broken")
            return self._build_feed(["headline"])

        fake.parse.side_effect = side_effect
        p = GoogleNewsNewsProvider()

        with patch("src.collector.providers.news.google_news_news_provider.parse_feed", fake.parse):
            with patch(
                "src.collector.providers.news.google_news_news_provider.record_pipeline_event"
            ) as logged:
                result = p.collect(_ctx())

        # 5 successful feeds × 1 item = 5 items. (Feed #2 raised.)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 5)
        # One warning event recorded for the failing feed.
        warn_events = [c for c in logged.call_args_list if c.args[2] == "news_provider_failed"]
        self.assertEqual(len(warn_events), 1)

    def test_uses_entry_source_when_provided(self) -> None:
        """NewsItem.source prefers the per-entry source override."""
        fake = MagicMock()
        entry = SimpleNamespace(
            title="X", published="", link="https://x",
            source={"title": "Bloomberg"},
        )
        fake.parse.return_value = SimpleNamespace(entries=[entry])
        p = GoogleNewsNewsProvider()

        with patch("src.collector.providers.news.google_news_news_provider.parse_feed", fake.parse):
            result = p.collect(_ctx())

        self.assertTrue(all(item.source == "Bloomberg" for item in result.items))

    def test_falls_back_to_feed_name_when_entry_source_missing(self) -> None:
        fake = MagicMock()
        # Entries with no `source` attribute → fallback to feed meta name.
        entry = SimpleNamespace(title="X", published="", link="https://x")
        fake.parse.return_value = SimpleNamespace(entries=[entry])
        p = GoogleNewsNewsProvider()

        with patch("src.collector.providers.news.google_news_news_provider.parse_feed", fake.parse):
            result = p.collect(_ctx())

        # Feed names include "Google News", "Yahoo Finance", "Reuters", etc.
        # Each feed's 1 entry inherits its feed name.
        got_sources = sorted({item.source for item in result.items})
        self.assertEqual(
            got_sources,
            sorted([
                "Associated Press", "CNBC", "Google News",
                "MarketWatch", "Reuters", "Yahoo Finance",
            ]),
        )


class BuildQueryTests(unittest.TestCase):
    def test_no_site_filter(self) -> None:
        item = WatchlistItem(ticker="AAPL", name="Apple Inc.", keywords=["iphone"])
        query = _build_query(item, "")
        self.assertIn("AAPL", query)
        self.assertIn("Apple", query)
        self.assertNotIn("site:", query)

    def test_with_site_filter(self) -> None:
        item = WatchlistItem(ticker="AAPL", name="Apple Inc.")
        query = _build_query(item, "reuters.com")
        self.assertIn("site:reuters.com", query)

    def test_strips_corporate_suffixes(self) -> None:
        item = WatchlistItem(ticker="MSFT", name="Microsoft Corporation")
        query = _build_query(item, "")
        self.assertIn("Microsoft", query)
        self.assertNotIn("Corporation", query)


class PlaceholderDetectionTests(unittest.TestCase):
    def test_detects_placeholder_tokens_case_insensitively(self) -> None:
        self.assertTrue(looks_like_unresolved_placeholder("META_TITLE_QUOTE - Yahoo Finance"))
        self.assertTrue(looks_like_unresolved_placeholder("Meta_Title_Quote - Yahoo Finance"))
        self.assertFalse(looks_like_unresolved_placeholder("Caterpillar earnings update - Yahoo Finance"))


if __name__ == "__main__":
    unittest.main()
