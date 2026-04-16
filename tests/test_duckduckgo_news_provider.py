"""Unit tests for src/collector/providers/news/duckduckgo_news_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.news_base import NewsContext
from src.collector.providers.news.duckduckgo_news_provider import (
    DuckDuckGoNewsProvider,
)
from src.types import NewsItem, WatchlistItem


def _ctx(*, extra: dict[str, object] | None = None) -> NewsContext:
    item = WatchlistItem(ticker="AAPL", name="Apple Inc.")
    return NewsContext(watchlist_item=item, run_date=date(2026, 4, 15), extra=extra or {})


class DuckDuckGoMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = DuckDuckGoNewsProvider()
        self.assertEqual(p.name, "duckduckgo")
        self.assertEqual(p.source_priority, 0)


class DuckDuckGoIsAvailableTests(unittest.TestCase):
    def test_returns_false_when_env_flag_disabled(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.is_env_flag_enabled",
            return_value=False,
        ):
            self.assertFalse(p.is_available(_ctx()))

    def test_honors_extra_cache_true(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.can_open_tcp_connection",
        ) as probe:
            self.assertTrue(
                p.is_available(_ctx(extra={"duckduckgo_available": True}))
            )
            probe.assert_not_called()

    def test_honors_extra_cache_false(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.can_open_tcp_connection",
        ) as probe:
            self.assertFalse(
                p.is_available(_ctx(extra={"duckduckgo_available": False}))
            )
            probe.assert_not_called()

    def test_falls_back_to_tcp_probe(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.can_open_tcp_connection",
            return_value=True,
        ):
            self.assertTrue(p.is_available(_ctx()))

    def test_probe_exception_returns_false(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.can_open_tcp_connection",
            side_effect=OSError("refused"),
        ):
            self.assertFalse(p.is_available(_ctx()))


class DuckDuckGoCollectTests(unittest.TestCase):
    def test_collect_happy_path(self) -> None:
        items = [
            NewsItem(title="Apple rumor", source="DuckDuckGo", link="https://x"),
            NewsItem(title="iPhone story", source="blog.com", link="https://y"),
        ]
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.news_search_module.search_news",
            return_value=items,
        ) as stub:
            result = p.collect(_ctx())
            stub.assert_called_once()
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 2)

    def test_collect_empty_is_still_success(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.news_search_module.search_news",
            return_value=[],
        ):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "success")
        self.assertEqual(result.items, [])

    def test_collect_exception_returns_failure(self) -> None:
        p = DuckDuckGoNewsProvider()
        with patch(
            "src.collector.providers.news.duckduckgo_news_provider.news_search_module.search_news",
            side_effect=RuntimeError("ddg rate limited"),
        ):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("ddg rate limited", result.reason)


if __name__ == "__main__":
    unittest.main()
