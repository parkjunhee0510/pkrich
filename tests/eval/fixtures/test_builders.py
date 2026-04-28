from __future__ import annotations

import unittest
from datetime import date

from tests.eval.fixtures.builders import (
    make_dataset,
    make_daily,
    make_summary,
)


class TestBuilders(unittest.TestCase):
    def test_make_dataset_default(self):
        ds = make_dataset()
        self.assertEqual((ds.window_end - ds.window_start).days, 13)
        self.assertGreater(len(ds.tickers), 0)
        for t in ds.tickers:
            self.assertEqual(len(ds.daily[t]), 14)

    def test_make_daily_overrides(self):
        d = make_daily(ticker="AAPL", as_of=date(2026, 4, 28),
                       summary="AAPL is at 273.43 USD (+0.10%).",
                       key_news=["headline 1"])
        self.assertEqual(d["payload"]["ticker"], "AAPL")
        self.assertIn("273.43", d["payload"]["summary"])

    def test_make_summary_token_usage(self):
        s = make_summary(date(2026, 4, 28), token_usage={"AAPL": 3000})
        self.assertEqual(s["model_usage"]["per_ticker_tokens"]["AAPL"], 3000)


if __name__ == "__main__":
    unittest.main()
