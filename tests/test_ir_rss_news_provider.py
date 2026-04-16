"""Unit tests for src/collector/providers/news/ir_rss_news_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.news_base import NewsContext
from src.collector.providers.news.ir_rss_news_provider import IRRSSNewsProvider
from src.types import NewsItem, WatchlistItem


_DEFAULT_FEED = "https://www.apple.com/newsroom/rss-feed.rss"


def _ctx(*, ir_rss_feeds: list[str] | None = None) -> NewsContext:
    # None means "use default feed"; [] means "explicitly empty".
    feeds = [_DEFAULT_FEED] if ir_rss_feeds is None else ir_rss_feeds
    item = WatchlistItem(
        ticker="AAPL",
        name="Apple Inc.",
        ir_rss_feeds=feeds,
    )
    return NewsContext(watchlist_item=item, run_date=date(2026, 4, 15))


class IRRSSProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = IRRSSNewsProvider()
        self.assertEqual(p.name, "ir_rss")
        self.assertEqual(p.source_priority, 2)


class IRRSSIsAvailableTests(unittest.TestCase):
    def test_returns_false_with_empty_feeds(self) -> None:
        p = IRRSSNewsProvider()
        self.assertFalse(p.is_available(_ctx(ir_rss_feeds=[])))

    def test_returns_true_with_feeds(self) -> None:
        p = IRRSSNewsProvider()
        self.assertTrue(p.is_available(_ctx()))

    def test_returns_false_when_env_flag_disabled(self) -> None:
        p = IRRSSNewsProvider()
        with patch(
            "src.collector.providers.news.ir_rss_news_provider.is_env_flag_enabled",
            return_value=False,
        ):
            self.assertFalse(p.is_available(_ctx()))


class IRRSSCollectTests(unittest.TestCase):
    def test_collect_returns_success_with_items(self) -> None:
        items = [
            NewsItem(
                title="Apple launches new product",
                source="Apple Newsroom",
                published_at="Mon, 14 Apr 2026 10:00:00 GMT",
                link="https://apple.com/newsroom/2026/04/launch",
            ),
        ]
        p = IRRSSNewsProvider()
        with patch(
            "src.collector.providers.news.ir_rss_news_provider.ir_rss_module.collect_ir_rss_news",
            return_value=items,
        ) as stub:
            result = p.collect(_ctx())
            stub.assert_called_once()
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)

    def test_collect_empty_is_still_success(self) -> None:
        p = IRRSSNewsProvider()
        with patch(
            "src.collector.providers.news.ir_rss_news_provider.ir_rss_module.collect_ir_rss_news",
            return_value=[],
        ):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "success")
        self.assertEqual(result.items, [])

    def test_collect_exception_returns_failure(self) -> None:
        p = IRRSSNewsProvider()
        with patch(
            "src.collector.providers.news.ir_rss_news_provider.ir_rss_module.collect_ir_rss_news",
            side_effect=RuntimeError("feed fetch failed"),
        ):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("feed fetch failed", result.reason)


if __name__ == "__main__":
    unittest.main()
