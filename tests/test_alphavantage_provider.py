"""Unit tests for src/collector/providers/alphavantage_provider.py.

Alpha Vantage has many sub-endpoints. We mock at the bundle boundary so
the tests assert extraction behavior, not network plumbing.
"""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.alphavantage_provider import (
    AlphaVantageProvider,
    _build_fields_from_bundle,
    _extract_overview_fields,
    _has_any_value,
)
from src.types import WatchlistItem


def _ctx(ticker: str = "AAPL") -> CollectionContext:
    return CollectionContext(
        watchlist_item=WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", sector="Tech"),
        run_date=date(2026, 4, 15),
    )


class AlphaVantageProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = AlphaVantageProvider()
        self.assertEqual(p.name, "alpha_vantage")
        self.assertEqual(p.priority, 3)
        self.assertIn("fundamentals", p.provides)
        self.assertIn("quarterly_financials", p.provides)
        self.assertIn("upcoming_events", p.provides)

    def test_is_available_requires_key_and_network(self) -> None:
        p = AlphaVantageProvider()
        # No key → unavailable regardless of network.
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": ""}, clear=False):
            self.assertFalse(p.is_available())
        # Key present but host unreachable.
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "demo"}, clear=False), patch(
            "src.collector.providers.alphavantage_provider.can_open_tcp_connection",
            return_value=False,
        ):
            self.assertFalse(p.is_available())
        # Key present and reachable.
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "demo"}, clear=False), patch(
            "src.collector.providers.alphavantage_provider.can_open_tcp_connection",
            return_value=True,
        ):
            self.assertTrue(p.is_available())
        # TCP probe raising should fail-closed.
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "demo"}, clear=False), patch(
            "src.collector.providers.alphavantage_provider.can_open_tcp_connection",
            side_effect=OSError,
        ):
            self.assertFalse(p.is_available())


class AlphaVantageProviderCollectTests(unittest.TestCase):
    """Tests for the collect() happy + failure paths."""

    def test_empty_bundle_returns_failure(self) -> None:
        p = AlphaVantageProvider()
        with patch(
            "src.collector.providers.alphavantage_provider.price_legacy._fetch_alpha_vantage_bundle",
            return_value={},
        ):
            result = p.collect("AAPL", _ctx())
        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "empty_bundle")

    def test_bundle_with_no_useful_fields_returns_failure(self) -> None:
        """If OVERVIEW is empty and quarterly/events yield nothing, fail out."""
        p = AlphaVantageProvider()
        with patch(
            "src.collector.providers.alphavantage_provider.price_legacy._fetch_alpha_vantage_bundle",
            return_value={"overview": {}, "earnings": {}, "income_statement": {}},
        ):
            result = p.collect("AAPL", _ctx())
        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "empty_extracted")

    def test_happy_path_populates_fundamentals(self) -> None:
        p = AlphaVantageProvider()
        bundle = {
            "overview": {
                "MarketCapitalization": "3500000000000",
                "PERatio": "30.5",
                "EPS": "6.20",
                "52WeekHigh": "260.10",
                "52WeekLow": "165.00",
                "50DayMovingAverage": "245.50",
                "200DayMovingAverage": "220.10",
                "ForwardEPS": "7.10",
                "AnalystTargetPrice": "275.00",
                "DividendYield": "0.005",
                "PriceToBookRatio": "45.2",
                "QuarterlyEarningsGrowthYOY": "0.12",
            },
            "earnings": {"quarterlyEarnings": []},
            "income_statement": {"quarterlyReports": []},
        }
        with patch(
            "src.collector.providers.alphavantage_provider.price_legacy._fetch_alpha_vantage_bundle",
            return_value=bundle,
        ):
            result = p.collect("AAPL", _ctx())
        self.assertTrue(result.ok)
        fields = result.data.fields
        # Non-"N/A" overview fields flow through.
        self.assertIn("market_cap", fields)
        self.assertIn("pe_ratio", fields)
        self.assertIn("forward_eps", fields)
        self.assertIn("analyst_target_price", fields)
        # "N/A" fields (Volume, AverageVolume not supplied) are dropped.
        self.assertNotIn("volume", fields)
        self.assertNotIn("avg_volume_3m", fields)

    def test_collect_never_raises_on_exception(self) -> None:
        p = AlphaVantageProvider()
        with patch(
            "src.collector.providers.alphavantage_provider.price_legacy._fetch_alpha_vantage_bundle",
            side_effect=RuntimeError("api boom"),
        ):
            result = p.collect("AAPL", _ctx())
        self.assertEqual(result.status, "failure")
        self.assertIn("api boom", result.reason)


class AlphaVantageProviderExtractionTests(unittest.TestCase):
    def test_extract_overview_drops_na_values(self) -> None:
        fields = _extract_overview_fields({
            "MarketCapitalization": "3.5e12",
            "PERatio": "None",   # formatter emits "N/A" for bad numerics
            "EPS": "6.20",
        })
        self.assertIn("market_cap", fields)
        self.assertIn("eps", fields)
        self.assertNotIn("pe_ratio", fields)   # "N/A" filtered out

    def test_build_fields_delegates_to_legacy_helpers(self) -> None:
        bundle = {
            "overview": {"EPS": "6.20"},
            "earnings": {"quarterlyEarnings": []},
            "income_statement": {"quarterlyReports": []},
        }
        fake_qf = [{"quarter": "2026-Q1", "revenue": "$120B", "eps": "6.20", "estimated_eps": "6.10", "surprise_pct": "+1.6%", "beat_miss": "beat", "fiscal_date": "2026-03-31", "operating_income": "$40B"}]
        fake_events = [{"type": "earnings", "date": "2026-04-30", "label": "실적 발표"}]
        with patch(
            "src.collector.providers.alphavantage_provider.price_legacy._extract_alpha_quarterly_financials",
            return_value=fake_qf,
        ), patch(
            "src.collector.providers.alphavantage_provider.price_legacy._extract_alpha_events",
            return_value=fake_events,
        ):
            fields = _build_fields_from_bundle(bundle, "AAPL", _ctx())
        self.assertEqual(fields["eps"], "6.20")
        self.assertEqual(fields["quarterly_financials"], fake_qf)
        self.assertEqual(fields["upcoming_events"], fake_events)

    def test_extraction_sub_failure_does_not_abort_whole_bundle(self) -> None:
        """If quarterly extraction throws, overview scalars still land."""
        bundle = {
            "overview": {"EPS": "6.20"},
            "earnings": {},
            "income_statement": {},
        }
        with patch(
            "src.collector.providers.alphavantage_provider.price_legacy._extract_alpha_quarterly_financials",
            side_effect=ValueError("bad data"),
        ), patch(
            "src.collector.providers.alphavantage_provider.price_legacy._extract_alpha_events",
            return_value=[],
        ):
            fields = _build_fields_from_bundle(bundle, "AAPL", _ctx())
        self.assertEqual(fields.get("eps"), "6.20")
        self.assertNotIn("quarterly_financials", fields)


class HelperTests(unittest.TestCase):
    def test_has_any_value(self) -> None:
        self.assertFalse(_has_any_value({"a": None, "b": "", "c": "N/A", "d": [], "e": {}}))
        self.assertTrue(_has_any_value({"a": "N/A", "b": "3.5e12"}))
        self.assertTrue(_has_any_value({"a": "", "b": [{"q": "2026-Q1"}]}))


if __name__ == "__main__":
    unittest.main()
