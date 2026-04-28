from __future__ import annotations

import unittest
from datetime import date, timedelta

from src.eval.checks.i4_input_size_drift import I4InputSizeDrift
from tests.eval.fixtures.builders import make_dataset, make_summary


class TestI4(unittest.TestCase):
    def test_pass_when_low_cv(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        summaries = {
            d: make_summary(d, token_usage={"AAPL": 3000 + (i % 2) * 50})
            for i, d in enumerate(days)
        }
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = I4InputSizeDrift().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_high_cv(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        summaries = {
            d: make_summary(d, token_usage={"AAPL": 1000 if i % 2 else 6000})
            for i, d in enumerate(days)
        }
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = I4InputSizeDrift().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
