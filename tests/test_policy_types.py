import unittest
from dataclasses import FrozenInstanceError

from src.types import PolicyEvent, TickerImpact, PolicyImpactReport


class TestPolicyTypes(unittest.TestCase):
    def test_policy_event_is_frozen(self):
        evt = PolicyEvent(
            id="abc", category="tariff", headline="h", summary="s",
            raw_excerpt="r", source_url="https://x", source_domain="x",
            published_at="2026-04-27T00:00:00Z", confidence=0.8,
        )
        with self.assertRaises(FrozenInstanceError):
            evt.headline = "y"

    def test_ticker_impact_score_signed(self):
        ti = TickerImpact(
            ticker="NVDA", direction="negative", strength="direct",
            score=-0.9, confidence=0.85, rationale="China revenue exposure",
        )
        self.assertLess(ti.score, 0)

    def test_report_has_aggregate(self):
        rpt = PolicyImpactReport(
            date="2026-04-27", events=[],
            impacts_by_event={}, impacts_by_ticker={},
            tailwind_scores={"NVDA": -0.5}, metadata={},
        )
        self.assertEqual(rpt.tailwind_scores["NVDA"], -0.5)


if __name__ == "__main__":
    unittest.main()
