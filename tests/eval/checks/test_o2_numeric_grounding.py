from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o2_numeric_grounding import O2NumericGrounding
from tests.eval.fixtures.builders import make_dataset


class TestO2(unittest.TestCase):
    def test_pass_when_summary_numbers_match_metrics(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d in ds.daily["AAPL"].values():
            d["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_pass_when_summary_numbers_match_data_snapshot(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d in ds.daily["AAPL"].values():
            d["payload"]["summary"] = "Apple traded at 100.00 USD (+0.50%)."
            d["payload"].pop("metrics", None)
            d["payload"]["data_snapshot"] = {"Price": "100.00 USD", "Daily Change": "+0.50%"}
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_summary_lies(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d in ds.daily["AAPL"].values():
            d["payload"]["summary"] = "Apple is at 999.00 USD (+50.00%)."
            d["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "fail")

    def test_warn_when_some_lies(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        days = sorted(ds.daily["AAPL"].keys())
        for d in days:
            ds.daily["AAPL"][d]["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        ds.daily["AAPL"][days[0]]["payload"]["summary"] = "999.00 USD (+50.00%)"
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "warn")

    def test_info_when_no_numeric_claims_are_evaluated(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for d in ds.daily["AAPL"].values():
            d["payload"]["summary"] = "No numeric claim here."
            d["payload"]["metrics"] = {"price": 100.00, "pct_change": 0.50}
        result = O2NumericGrounding().run(ds)
        self.assertEqual(result.severity, "info")
        self.assertEqual(result.metrics["sample_count"], 0.0)


if __name__ == "__main__":
    unittest.main()
