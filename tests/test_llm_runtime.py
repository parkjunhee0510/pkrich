from __future__ import annotations

import unittest

from src.analyzer.llm_runtime import parse_ticker_batch


class ParseTickerBatchTests(unittest.TestCase):
    def test_allows_missing_tickers_for_partial_batch_repair(self) -> None:
        content = """
        {
          "tickers": [
            {"ticker": "AAPL", "summary": "ok"},
            {"ticker": "AMD", "summary": "ok"}
          ]
        }
        """
        parsed = parse_ticker_batch(content, ["AAPL", "AMD", "PL"])
        self.assertEqual(len(parsed), 2)
        self.assertEqual({entry["ticker"] for entry in parsed}, {"AAPL", "AMD"})

    def test_rejects_unexpected_ticker(self) -> None:
        content = """
        {
          "tickers": [
            {"ticker": "AAPL", "summary": "ok"},
            {"ticker": "MSFT", "summary": "bad"}
          ]
        }
        """
        with self.assertRaises(ValueError):
            parse_ticker_batch(content, ["AAPL", "AMD"])


if __name__ == "__main__":
    unittest.main()
