"""Unit tests for src/collector/providers/stooq_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.stooq_provider import StooqProvider
from src.types import WatchlistItem


def _ctx(ticker: str = "AAPL") -> CollectionContext:
    return CollectionContext(
        watchlist_item=WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", sector="Tech"),
        run_date=date(2026, 4, 15),
    )


class StooqProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = StooqProvider()
        self.assertEqual(p.name, "stooq")
        self.assertEqual(p.priority, 3)  # fallback tier
        self.assertEqual(p.provides, {"price"})

    def test_is_available_requires_network_and_flag(self) -> None:
        p = StooqProvider()
        with patch("src.collector.providers.stooq_provider.is_env_flag_enabled", return_value=False):
            self.assertFalse(p.is_available())
        with patch("src.collector.providers.stooq_provider.is_env_flag_enabled", return_value=True), \
             patch("src.collector.providers.stooq_provider.can_open_tcp_connection", return_value=False):
            self.assertFalse(p.is_available())
        with patch("src.collector.providers.stooq_provider.is_env_flag_enabled", return_value=True), \
             patch("src.collector.providers.stooq_provider.can_open_tcp_connection", return_value=True):
            self.assertTrue(p.is_available())


class StooqProviderCollectTests(unittest.TestCase):
    def test_collect_returns_success_with_price_and_change(self) -> None:
        p = StooqProvider()
        with patch(
            "src.collector.providers.stooq_provider.price_legacy._fetch_stooq_price_snapshot",
            return_value=(247.96, 1.2),
        ):
            result = p.collect("AAPL", _ctx())

        self.assertTrue(result.ok)
        self.assertEqual(result.data.fields["price"], 247.96)
        self.assertEqual(result.data.fields["change_percent"], 1.2)
        self.assertEqual(result.data.ticker, "AAPL")

    def test_collect_returns_failure_when_no_data(self) -> None:
        p = StooqProvider()
        with patch(
            "src.collector.providers.stooq_provider.price_legacy._fetch_stooq_price_snapshot",
            return_value=(None, None),
        ):
            result = p.collect("XYZ", _ctx("XYZ"))
        self.assertEqual(result.status, "failure")
        self.assertIn("no_stooq_data", result.reason)

    def test_collect_never_raises_on_exception(self) -> None:
        p = StooqProvider()
        with patch(
            "src.collector.providers.stooq_provider.price_legacy._fetch_stooq_price_snapshot",
            side_effect=RuntimeError("network broken"),
        ):
            result = p.collect("AAPL", _ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("network broken", result.reason)


if __name__ == "__main__":
    unittest.main()
