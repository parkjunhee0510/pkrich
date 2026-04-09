from __future__ import annotations

import json
import unittest

from src.analyzer.research_note import _parse_and_validate_response
from src.types import WatchlistItem


class AnalyzerSchemaTests(unittest.TestCase):
    def test_parse_and_validate_response_accepts_valid_payload(self) -> None:
        content = json.dumps(
            {
                "tickers": [
                    {
                        "ticker": "AAPL",
                        "summary": "Apple summary",
                        "key_news": ["Headline 1"],
                        "financial_highlights": ["Market cap: 1.00T"],
                        "risks_or_watchpoints": ["Watch services growth"],
                        "signal_or_takeaway": "Monitor the next earnings print.",
                        "trade_frame": {
                            "bull_scenario": "Bull case",
                            "base_scenario": "Base case",
                            "bear_scenario": "Bear case",
                            "invalidation_price": "Below 95",
                            "watch_period": "Next 5 trading days",
                        },
                    }
                ]
            }
        )

        result = _parse_and_validate_response(
            content,
            [WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology")],
        )

        self.assertEqual(result[0]["ticker"], "AAPL")
        self.assertEqual(result[0]["key_news"], ["Headline 1"])

    def test_parse_and_validate_response_rejects_unexpected_ticker(self) -> None:
        content = json.dumps(
            {
                "tickers": [
                    {
                        "ticker": "MSFT",
                        "summary": "Microsoft summary",
                        "key_news": ["Headline 1"],
                        "financial_highlights": ["Market cap: 1.00T"],
                        "risks_or_watchpoints": ["Watch cloud growth"],
                        "signal_or_takeaway": "Monitor Azure demand.",
                        "trade_frame": {
                            "bull_scenario": "Bull case",
                            "base_scenario": "Base case",
                            "bear_scenario": "Bear case",
                            "invalidation_price": "Below 95",
                            "watch_period": "Next 5 trading days",
                        },
                    }
                ]
            }
        )

        with self.assertRaises(ValueError):
            _parse_and_validate_response(
                content,
                [WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology")],
            )

    def test_parse_and_validate_response_rejects_empty_strings(self) -> None:
        content = json.dumps(
            {
                "tickers": [
                    {
                        "ticker": "AAPL",
                        "summary": "",
                        "key_news": ["Headline 1"],
                        "financial_highlights": ["Market cap: 1.00T"],
                        "risks_or_watchpoints": ["Watch services growth"],
                        "signal_or_takeaway": "Monitor the next earnings print.",
                        "trade_frame": {
                            "bull_scenario": "Bull case",
                            "base_scenario": "Base case",
                            "bear_scenario": "Bear case",
                            "invalidation_price": "Below 95",
                            "watch_period": "Next 5 trading days",
                        },
                    }
                ]
            }
        )

        with self.assertRaises(ValueError):
            _parse_and_validate_response(
                content,
                [WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology")],
            )


if __name__ == "__main__":
    unittest.main()
