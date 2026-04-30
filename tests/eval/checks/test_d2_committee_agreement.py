from __future__ import annotations

import unittest
from datetime import date

from src.eval.checks.d2_committee_agreement import D2CommitteeAgreement
from src.eval.data_sources import PipelineEvent
from tests.eval.fixtures.builders import make_dataset


def _committee_event(d, ticker, role, action):
    return PipelineEvent(
        date=d, component="committee", severity="info",
        message="role_decision",
        detail={"role": role, "action": action},
        ticker=ticker, module="committee",
    )


class TestD2(unittest.TestCase):
    def test_pass_when_roles_agree(self):
        d = date(2026, 4, 28)
        logs = [
            _committee_event(d, "AAPL", "pm_economy", "buy"),
            _committee_event(d, "AAPL", "pm_deep", "buy"),
            _committee_event(d, "AAPL", "risk", "buy"),
        ]
        ds = make_dataset(tickers=("AAPL",), end=d, logs=logs)
        result = D2CommitteeAgreement().run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_roles_disagree(self):
        d = date(2026, 4, 28)
        logs = [
            _committee_event(d, "AAPL", "pm_economy", "buy"),
            _committee_event(d, "AAPL", "pm_deep", "watch"),
            _committee_event(d, "AAPL", "risk", "avoid"),
        ]
        ds = make_dataset(tickers=("AAPL",), end=d, logs=logs)
        result = D2CommitteeAgreement().run(ds)
        self.assertEqual(result.severity, "fail")

    def test_info_when_no_committee_decisions_are_evaluated(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28), logs=())
        result = D2CommitteeAgreement().run(ds)
        self.assertEqual(result.severity, "info")
        self.assertEqual(result.metrics["sample_count"], 0.0)


if __name__ == "__main__":
    unittest.main()
