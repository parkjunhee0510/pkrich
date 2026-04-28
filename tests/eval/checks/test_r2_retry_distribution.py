from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.r2_retry_distribution import R2RetryDistribution
from src.eval.data_sources import PipelineEvent
from tests.eval.fixtures.builders import make_dataset


def _retry(d, ticker, module="research_note"):
    return PipelineEvent(date=d, component="analyzer", severity="warn",
                         message="retry", detail={}, ticker=ticker, module=module)


class TestR2(unittest.TestCase):
    def test_pass_when_few_retries(self):
        d = date(2026, 4, 28)
        ds = make_dataset(tickers=("AAPL",), end=d, logs=[_retry(d, "AAPL")])
        result = R2RetryDistribution().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_hot_ticker(self):
        d = date(2026, 4, 28)
        logs = [_retry(d, "AAPL") for _ in range(10)]
        ds = make_dataset(tickers=("AAPL",), end=d, logs=logs)
        result = R2RetryDistribution().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
