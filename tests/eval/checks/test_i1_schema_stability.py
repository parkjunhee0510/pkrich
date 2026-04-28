from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.i1_schema_stability import I1SchemaStability
from tests.eval.fixtures.builders import make_dataset


class TestI1(unittest.TestCase):
    def test_pass_when_all_fields_present(self):
        ds = make_dataset(tickers=("AAPL",))
        result = I1SchemaStability().run(ds)
        self.assertEqual(result.severity, "pass")
        self.assertEqual(result.pass_rate, 1.0)
        self.assertEqual(result.findings, ())

    def test_warn_when_one_field_missing_one_day(self):
        end = date(2026, 4, 28)
        ds = make_dataset(tickers=("AAPL",), end=end)
        # Drop key_news on the most recent day → 1 of (14*5)=70 fields missing ≈ 1.43%.
        # Wait — that's <2%, so it would be pass. Drop one whole day's fields.
        # Actually, the threshold is "missing field rate" across (record × required_field).
        # 14 days × 5 required = 70. Need rate between 2% and 10% → drop 2 to 7 fields.
        # Drop key_news on 4 days → 4/70 ≈ 5.7% → warn band.
        days = sorted(ds.daily["AAPL"].keys())
        for d in days[:4]:
            ds.daily["AAPL"][d]["payload"].pop("key_news", None)
        result = I1SchemaStability().run(ds)
        self.assertEqual(result.severity, "warn")

    def test_fail_when_many_missing(self):
        end = date(2026, 4, 28)
        ds = make_dataset(tickers=("AAPL",), end=end)
        for d, payload in ds.daily["AAPL"].items():
            payload["payload"].pop("key_news", None)
            payload["payload"].pop("news_references", None)
        result = I1SchemaStability().run(ds)
        self.assertEqual(result.severity, "fail")
        self.assertGreater(len(result.findings), 0)


if __name__ == "__main__":
    unittest.main()
