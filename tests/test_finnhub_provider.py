"""Unit tests for src/collector/providers/finnhub_provider.py."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.finnhub_provider import FinnhubProvider
from src.types import WatchlistItem


def _ctx(ticker: str = "AAPL") -> CollectionContext:
    return CollectionContext(
        watchlist_item=WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", sector="Tech"),
        run_date=date(2026, 4, 15),
    )


class FinnhubProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = FinnhubProvider()
        self.assertEqual(p.name, "finnhub")
        self.assertEqual(p.priority, 2)
        self.assertEqual(p.provides, {"recommendation_trends"})

    def test_is_available_delegates_to_module(self) -> None:
        p = FinnhubProvider()
        with patch(
            "src.collector.providers.finnhub_provider.finnhub_module.is_finnhub_ready",
            return_value=True,
        ):
            self.assertTrue(p.is_available())
        with patch(
            "src.collector.providers.finnhub_provider.finnhub_module.is_finnhub_ready",
            return_value=False,
        ):
            self.assertFalse(p.is_available())
        # If is_finnhub_ready raises, is_available returns False (defensive).
        with patch(
            "src.collector.providers.finnhub_provider.finnhub_module.is_finnhub_ready",
            side_effect=RuntimeError,
        ):
            self.assertFalse(p.is_available())


class FinnhubProviderCollectTests(unittest.TestCase):
    def test_collect_returns_success_with_recommendation_trends(self) -> None:
        trends = [
            {"period": "2026-03-01", "strong_buy": "5", "buy": "10", "hold": "3", "sell": "1", "strong_sell": "0", "total": "19", "consensus": "Buy", "trend": "upgrading"},
            {"period": "2025-12-01", "strong_buy": "4", "buy": "9", "hold": "4", "sell": "1", "strong_sell": "0", "total": "18", "consensus": "Buy"},
        ]
        p = FinnhubProvider()
        with patch(
            "src.collector.providers.finnhub_provider.finnhub_module.collect_finnhub_recommendations",
            return_value=trends,
        ):
            result = p.collect("AAPL", _ctx())

        self.assertTrue(result.ok)
        self.assertEqual(result.data.ticker, "AAPL")
        self.assertEqual(result.data.fields["recommendation_trends"], trends)

    def test_collect_returns_failure_when_empty(self) -> None:
        p = FinnhubProvider()
        with patch(
            "src.collector.providers.finnhub_provider.finnhub_module.collect_finnhub_recommendations",
            return_value=[],
        ):
            result = p.collect("XYZ", _ctx("XYZ"))
        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "no_recommendations")

    def test_collect_never_raises_on_exception(self) -> None:
        p = FinnhubProvider()
        with patch(
            "src.collector.providers.finnhub_provider.finnhub_module.collect_finnhub_recommendations",
            side_effect=RuntimeError("network broken"),
        ):
            result = p.collect("AAPL", _ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("network broken", result.reason)


if __name__ == "__main__":
    unittest.main()
