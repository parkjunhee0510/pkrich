"""Unit tests for src/collector/providers/fmp_provider.py.

FMP hits several endpoints per ticker. We mock the fmp module entirely to
avoid network calls and focus on the provider's composition rules:
  * Core (metrics / ratios / dividends / profile) always attempted
  * Extended endpoints gated by should_collect_fmp_extended()
  * Each endpoint is independently failure-tolerant
  * Empty responses result in ProviderResult.failure
"""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.fmp_provider import (
    FMPProvider,
    _has_any_value,
    _safe,
    _safe_dict,
    _safe_list,
)
from src.types import WatchlistItem


def _ctx(ticker: str = "AAPL") -> CollectionContext:
    return CollectionContext(
        watchlist_item=WatchlistItem(ticker=ticker, name=f"{ticker} Inc.", sector="Tech"),
        run_date=date(2026, 4, 15),
    )


class FMPProviderMetadataTests(unittest.TestCase):
    def test_metadata(self) -> None:
        p = FMPProvider()
        self.assertEqual(p.name, "fmp")
        self.assertEqual(p.priority, 2)
        self.assertIn("fundamentals", p.provides)
        self.assertIn("analyst_estimates", p.provides)

    def test_is_available_delegates_to_module(self) -> None:
        p = FMPProvider()
        with patch("src.collector.providers.fmp_provider.fmp_module.is_fmp_ready", return_value=True):
            self.assertTrue(p.is_available())
        with patch("src.collector.providers.fmp_provider.fmp_module.is_fmp_ready", return_value=False):
            self.assertFalse(p.is_available())
        # If is_fmp_ready raises, is_available returns False.
        with patch("src.collector.providers.fmp_provider.fmp_module.is_fmp_ready", side_effect=RuntimeError):
            self.assertFalse(p.is_available())


class FMPProviderCoreTests(unittest.TestCase):
    """Core endpoints (always attempted) — metrics/ratios/dividends/profile."""

    def _patch_core(self, metrics=None, ratios=None, dividends=None, profile=None):
        return (
            patch(
                "src.collector.providers.fmp_provider.fmp_module.collect_fmp_key_metrics",
                return_value=metrics or {},
            ),
            patch(
                "src.collector.providers.fmp_provider.fmp_module.collect_fmp_financial_ratios",
                return_value=ratios or {},
            ),
            patch(
                "src.collector.providers.fmp_provider.fmp_module.collect_fmp_dividend_history",
                return_value=dividends or {},
            ),
            patch(
                "src.collector.providers.fmp_provider.fmp_module.collect_fmp_company_profile",
                return_value=profile or {},
            ),
            patch(
                "src.collector.providers.fmp_provider.fmp_module.should_collect_fmp_extended",
                return_value=False,
            ),
        )

    def test_happy_path_merges_metrics(self) -> None:
        p = FMPProvider()
        patchers = self._patch_core(
            metrics={"roic": "12.5"},
            ratios={"debt_to_equity": "0.5"},
            dividends={"dividend_growth_5y": "5.0"},
            profile={"industry": "Consumer Electronics", "sector": "Technology", "beta": "1.18"},
        )
        for patcher in patchers:
            patcher.start()
        try:
            result = p.collect("AAPL", _ctx())
        finally:
            for patcher in patchers:
                patcher.stop()

        self.assertTrue(result.ok)
        metrics = result.data.fields["fundamental_metrics"]
        self.assertEqual(metrics["roic"], "12.5")
        self.assertEqual(metrics["debt_to_equity"], "0.5")
        self.assertEqual(metrics["dividend_growth_5y"], "5.0")
        self.assertEqual(metrics["industry"], "Consumer Electronics")
        self.assertEqual(metrics["beta"], "1.18")
        self.assertEqual(result.data.fields["sector"], "Technology")

    def test_all_endpoints_empty_returns_failure(self) -> None:
        p = FMPProvider()
        patchers = self._patch_core()  # everything empty
        for patcher in patchers:
            patcher.start()
        try:
            result = p.collect("AAPL", _ctx())
        finally:
            for patcher in patchers:
                patcher.stop()
        self.assertEqual(result.status, "failure")
        self.assertEqual(result.reason, "empty_response")


class FMPProviderExtendedTests(unittest.TestCase):
    """Extended endpoints — only fire when should_collect_fmp_extended()."""

    def test_extended_disabled_skips_extended_endpoints(self) -> None:
        p = FMPProvider()
        with patch(
            "src.collector.providers.fmp_provider.fmp_module.should_collect_fmp_extended",
            return_value=False,
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_key_metrics",
            return_value={"roic": "12"},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_financial_ratios",
            return_value={},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_dividend_history",
            return_value={},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_company_profile",
            return_value={},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_analyst_estimates",
        ) as m_est, patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_insider_trading",
        ) as m_ins:
            result = p.collect("AAPL", _ctx())

        self.assertTrue(result.ok)
        m_est.assert_not_called()
        m_ins.assert_not_called()

    def test_extended_enabled_populates_optional_fields(self) -> None:
        p = FMPProvider()
        with patch(
            "src.collector.providers.fmp_provider.fmp_module.should_collect_fmp_extended",
            return_value=True,
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_key_metrics", return_value={}
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_financial_ratios", return_value={}
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_dividend_history", return_value={}
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_company_profile", return_value={}
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_analyst_estimates",
            return_value={"direction": "up"},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_insider_trading",
            return_value=[{"filer": "CEO"}],
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_institutional_holders",
            return_value={"delta": "+2"},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_earnings_surprises",
            return_value=[{"q": "2026-Q1"}],
        ):
            result = p.collect("AAPL", _ctx())

        self.assertTrue(result.ok)
        fields = result.data.fields
        self.assertEqual(fields["analyst_estimate_revisions"]["direction"], "up")
        self.assertEqual(fields["insider_transactions"][0]["filer"], "CEO")
        self.assertEqual(fields["institutional_changes"]["delta"], "+2")
        self.assertEqual(fields["fmp_earnings_surprises"][0]["q"], "2026-Q1")


class FMPProviderResilienceTests(unittest.TestCase):
    def test_endpoint_exception_does_not_kill_collect(self) -> None:
        """A single endpoint throwing shouldn't abort the other endpoints."""
        p = FMPProvider()
        with patch(
            "src.collector.providers.fmp_provider.fmp_module.should_collect_fmp_extended",
            return_value=False,
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_key_metrics",
            side_effect=RuntimeError("429"),
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_financial_ratios",
            return_value={"gross_margin": "40"},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_dividend_history",
            return_value={},
        ), patch(
            "src.collector.providers.fmp_provider.fmp_module.collect_fmp_company_profile",
            return_value={},
        ):
            result = p.collect("AAPL", _ctx())
        self.assertTrue(result.ok)
        self.assertEqual(result.data.fields["fundamental_metrics"]["gross_margin"], "40")


class HelperTests(unittest.TestCase):
    def test_safe_returns_default_on_exception(self) -> None:
        self.assertEqual(_safe(lambda: (_ for _ in ()).throw(RuntimeError()), default=5), 5)
        self.assertEqual(_safe(lambda: 42, default=0), 42)

    def test_safe_dict_rejects_non_dict(self) -> None:
        self.assertEqual(_safe_dict(lambda: [1, 2]), {})

    def test_safe_list_rejects_non_list(self) -> None:
        self.assertEqual(_safe_list(lambda: {"k": "v"}), [])

    def test_has_any_value_ignores_empty_collections(self) -> None:
        self.assertFalse(_has_any_value({"a": None, "b": "", "c": "N/A", "d": {}, "e": []}))
        self.assertTrue(_has_any_value({"a": "", "b": {"k": "v"}}))


if __name__ == "__main__":
    unittest.main()
