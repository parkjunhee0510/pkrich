from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.i2_missingness import I2Missingness
from tests.eval.fixtures.builders import make_dataset


class TestI2(unittest.TestCase):
    def test_pass_when_all_news_present(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        result = I2Missingness().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_news_references_empty_majority(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for d in days[:12]:
            ds.daily["AAPL"][d]["payload"]["news_references"] = []
        result = I2Missingness().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
