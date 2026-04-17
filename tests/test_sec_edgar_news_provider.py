"""Unit tests for src/collector/providers/news/sec_edgar_news_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.news_base import NewsContext
from src.collector.providers.news.sec_edgar_news_provider import SECEdgarNewsProvider
from src.types import NewsItem, WatchlistItem


def _ctx(
    *,
    ticker: str = "AAPL",
    cik: str = "0000320193",
    extra: dict[str, object] | None = None,
) -> NewsContext:
    item = WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", cik=cik)
    return NewsContext(watchlist_item=item, run_date=date(2026, 4, 15), extra=extra or {})


class SECEdgarNewsProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = SECEdgarNewsProvider()
        self.assertEqual(p.name, "sec_edgar")
        self.assertEqual(p.source_priority, 4)


class SECEdgarIsAvailableTests(unittest.TestCase):
    def test_returns_false_without_cik(self) -> None:
        p = SECEdgarNewsProvider()
        self.assertFalse(p.is_available(_ctx(cik="")))

    def test_returns_false_when_env_flag_disabled(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.is_env_flag_enabled",
            return_value=False,
        ):
            self.assertFalse(p.is_available(_ctx()))

    def test_honors_extra_cached_probe_true(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.can_open_tcp_connection",
        ) as probe:
            # Should NOT reach the TCP probe — cache wins.
            self.assertTrue(p.is_available(_ctx(extra={"sec_edgar_available": True})))
            probe.assert_not_called()

    def test_honors_extra_cached_probe_false(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.can_open_tcp_connection",
        ) as probe:
            self.assertFalse(p.is_available(_ctx(extra={"sec_edgar_available": False})))
            probe.assert_not_called()

    def test_falls_back_to_tcp_probe_when_no_cache(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.can_open_tcp_connection",
            return_value=True,
        ):
            self.assertTrue(p.is_available(_ctx()))

    def test_tcp_probe_exception_returns_false(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.can_open_tcp_connection",
            side_effect=OSError("refused"),
        ):
            self.assertFalse(p.is_available(_ctx()))


class SECEdgarCollectTests(unittest.TestCase):
    def test_collect_returns_success_with_items(self) -> None:
        items = [
            NewsItem(
                title="Apple filed 8-K",
                source="SEC EDGAR",
                published_at="Mon, 14 Apr 2026 10:00:00 GMT",
                link="https://sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193",
                form_type="8-K",
                item_number="2.02",
                catalyst_type="hard",
                importance_score=200,
            ),
        ]
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.sec_edgar_module.collect_sec_edgar_news",
            return_value=items,
        ) as stub:
            result = p.collect(_ctx())
            stub.assert_called_once()
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)

    def test_collect_empty_is_still_success(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.sec_edgar_module.collect_sec_edgar_news",
            return_value=[],
        ):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "success")
        self.assertEqual(result.items, [])

    def test_collect_exception_returns_failure(self) -> None:
        p = SECEdgarNewsProvider()
        with patch(
            "src.collector.providers.news.sec_edgar_news_provider.sec_edgar_module.collect_sec_edgar_news",
            side_effect=RuntimeError("edgar broke"),
        ):
            result = p.collect(_ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("edgar broke", result.reason)


if __name__ == "__main__":
    unittest.main()
