from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.sector_etf_provider import SectorEtfProvider
from src.types import WatchlistItem


class _FakeTicker:
    def __init__(self, history_by_symbol, symbol: str) -> None:
        self._history_by_symbol = history_by_symbol
        self._symbol = symbol

    def history(self, period: str, interval: str):
        return self._history_by_symbol[self._symbol]


class _FakeYFinance:
    def __init__(self, history_by_symbol) -> None:
        self._history_by_symbol = history_by_symbol

    def Ticker(self, symbol: str) -> _FakeTicker:
        return _FakeTicker(self._history_by_symbol, symbol)


class SectorEtfProviderTests(unittest.TestCase):
    def test_collects_rs_vs_sector_etf(self) -> None:
        import pandas as pd

        dates = pd.to_datetime(["2026-03-13", "2026-04-15"])
        history_by_symbol = {
            "AMD": pd.DataFrame({"Close": [100.0, 110.0]}, index=dates),
            "XLK": pd.DataFrame({"Close": [100.0, 103.0]}, index=dates),
        }
        provider = SectorEtfProvider()
        provider._sector_etf_map = {"Technology": "XLK"}  # type: ignore[attr-defined]
        ctx = CollectionContext(
            watchlist_item=WatchlistItem(ticker="AMD", name="AMD", sector="Technology"),
            run_date=date(2026, 4, 15),
        )

        with patch.object(provider, "_get_yfinance_module", return_value=_FakeYFinance(history_by_symbol)):
            result = provider.collect("AMD", ctx)

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data.fields["rs_vs_sector_etf"], "+7.00%")

    def test_skips_without_mapping(self) -> None:
        provider = SectorEtfProvider()
        provider._sector_etf_map = {}  # type: ignore[attr-defined]
        ctx = CollectionContext(
            watchlist_item=WatchlistItem(ticker="KO", name="KO", sector="Consumer Staples"),
            run_date=date(2026, 4, 15),
        )

        result = provider.collect("KO", ctx)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "no_sector_etf_mapping")


if __name__ == "__main__":
    unittest.main()
