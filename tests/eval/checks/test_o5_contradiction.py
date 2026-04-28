from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.o5_contradiction import O5Contradiction
from tests.eval.fixtures.builders import make_dataset


class TestO5(unittest.TestCase):
    def test_pass_when_three_signals_agree(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["summary"] = "긍정적 모멘텀 지속, 매수 검토."
            record["payload"]["risk_assessment"] = {"severity": "low"}
            record["payload"]["research_narrative"] = {"outlook": "positive"}
        result = O5Contradiction().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_disagree(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        for record in ds.daily["AAPL"].values():
            record["payload"]["summary"] = "강한 부정적 모멘텀, 매도 권고."
            record["payload"]["risk_assessment"] = {"severity": "low"}
            record["payload"]["research_narrative"] = {"outlook": "positive"}
        result = O5Contradiction().run(ds)
        self.assertEqual(result.severity, "fail")


if __name__ == "__main__":
    unittest.main()
