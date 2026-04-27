import json
import os
import tempfile
import unittest

from src.types import PolicyEvent, TickerImpact, PolicyImpactReport
from src.output.policy_json import write_policy_impact_json


class TestPolicyJsonExport(unittest.TestCase):
    def test_writes_well_formed_json(self):
        evt = PolicyEvent(
            "evt1",
            "tariff",
            "h",
            "s",
            "r",
            "https://x",
            "x",
            "2026-04-27T00:00:00Z",
            0.8,
        )
        imp = TickerImpact("NVDA", "negative", "direct", -0.8, 0.9, "r")
        rpt = PolicyImpactReport(
            date="2026-04-27",
            events=[evt],
            impacts_by_event={"evt1": [imp]},
            impacts_by_ticker={"NVDA": [imp]},
            tailwind_scores={"NVDA": -0.72},
            metadata={"tokens_in": 100},
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "policy_impact.json")
            write_policy_impact_json(rpt, p)
            with open(p, encoding="utf-8") as f:
                payload = json.load(f)
        self.assertEqual(payload["date"], "2026-04-27")
        self.assertEqual(payload["tailwind_scores"]["NVDA"], -0.72)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["impacts_by_ticker"]["NVDA"][0]["score"], -0.8)


if __name__ == "__main__":
    unittest.main()
