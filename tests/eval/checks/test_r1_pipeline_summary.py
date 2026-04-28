from __future__ import annotations

import unittest
from datetime import date, timedelta

from src.eval.checks.r1_pipeline_summary import R1PipelineSummary
from tests.eval.fixtures.builders import make_dataset, make_summary


class TestR1(unittest.TestCase):
    def test_pass_when_low_fallback_rate(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        summaries = {d: make_summary(d, fallback_count=0) for d in days}
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = R1PipelineSummary().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_high_fallback_rate(self):
        end = date(2026, 4, 28)
        days = [end - timedelta(days=i) for i in range(14)]
        summaries = {d: make_summary(d, fallback_count=20) for d in days}
        ds = make_dataset(tickers=("AAPL",), end=end, summary_overrides=summaries)
        result = R1PipelineSummary().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
