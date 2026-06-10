from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from src.collector.base import CollectionContext
from src.collector.providers.toss_invest_provider import TossInvestProvider
from src.types import WatchlistItem


class _FakeTossClient:
    is_configured = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def get_prices(self, symbols: list[str]) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("boom")
        return {
            "result": [
                {"symbol": symbols[0], "lastPrice": "200.00", "currency": "USD"},
            ]
        }

    def get_candles(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 2,
        adjusted: bool = True,
    ) -> dict[str, object]:
        del symbol, interval, count, adjusted
        return {
            "result": {
                "candles": [
                    {
                        "timestamp": "2026-06-03T00:00:00+00:00",
                        "openPrice": "198.00",
                        "highPrice": "203.00",
                        "lowPrice": "197.00",
                        "closePrice": "200.00",
                        "volume": "1000",
                        "currency": "USD",
                    },
                    {
                        "timestamp": "2026-06-02T00:00:00+00:00",
                        "openPrice": "190.00",
                        "highPrice": "195.00",
                        "lowPrice": "189.00",
                        "closePrice": "190.00",
                        "volume": "900",
                        "currency": "USD",
                    },
                ]
            }
        }

    def get_stocks(self, symbols: list[str]) -> dict[str, object]:
        return {
            "result": [
                {
                    "symbol": symbols[0],
                    "name": "애플",
                    "englishName": "Apple Inc.",
                    "market": "NASDAQ",
                    "securityType": "FOREIGN_STOCK",
                    "status": "ACTIVE",
                    "currency": "USD",
                    "sharesOutstanding": "15500000000",
                }
            ]
        }

    def get_stock_warnings(self, symbol: str) -> dict[str, object]:
        del symbol
        return {
            "result": [
                {
                    "warningType": "INVESTMENT_WARNING",
                    "exchange": "NASDAQ",
                    "startDate": "2026-06-01",
                    "endDate": None,
                }
            ]
        }


def _ctx(ticker: str = "AAPL") -> CollectionContext:
    return CollectionContext(
        watchlist_item=WatchlistItem(ticker=ticker, name="Apple", sector="Technology"),
        run_date=date(2026, 6, 4),
    )


class TossInvestProviderTests(unittest.TestCase):
    def test_is_unavailable_without_credentials(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            provider = TossInvestProvider()

            self.assertFalse(provider.is_available())

    def test_collect_normalizes_price_candles_stock_metadata_and_warnings(self) -> None:
        provider = TossInvestProvider(client=_FakeTossClient())

        result = provider.collect("AAPL", _ctx())

        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.data)
        fields = result.data.fields if result.data else {}
        self.assertEqual(fields["price"], 200.0)
        self.assertAlmostEqual(fields["change_percent"], 5.26)
        self.assertEqual(fields["currency"], "USD")
        self.assertEqual(fields["close_price"], "200.00")
        self.assertEqual(fields["day_volume"], "1000")
        self.assertEqual(fields["historical_prices"][0]["date"], "2026-06-03")
        self.assertEqual(fields["historical_prices"][0]["close"], "200.00")
        self.assertEqual(fields["fundamental_metrics"]["toss_market"], "NASDAQ")
        self.assertEqual(fields["fundamental_metrics"]["shares_outstanding"], "15500000000")
        self.assertEqual(fields["upcoming_events"][0]["type"], "stock_warning")
        self.assertEqual(fields["upcoming_events"][0]["label"], "INVESTMENT_WARNING")

    def test_collect_returns_failure_when_client_raises(self) -> None:
        provider = TossInvestProvider(client=_FakeTossClient(fail=True))

        result = provider.collect("AAPL", _ctx())

        self.assertEqual(result.status, "failure")
        self.assertIn("exception", result.reason)


if __name__ == "__main__":
    unittest.main()
