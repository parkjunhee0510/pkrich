"""Policy golden regression test (Task 9).

Runs the real LLM against 12 well-known policy events with known top-impact
tickers. Verifies that aggregate top-3 directional accuracy is ≥ 80%.

Default: SKIPPED unless `OPENAI_API_KEY` is set AND `POLICY_GOLDEN_OFFLINE`
is unset. CI/local devs see SKIP automatically; pre-merge / pre-deploy runs
should set the keys and unset the offline flag manually:

    POLICY_GOLDEN_OFFLINE= OPENAI_API_KEY=sk-... \
        python -m unittest tests.test_policy_golden -v

The fixture lives at tests/fixtures/policy_events_golden.json and covers:
chips_act, export_control, tariff, IRA solar, IRA EV, FDA approval,
FDA warning, antitrust, defense, energy, interest_rate, banking.
"""

from __future__ import annotations

import json
import os
import unittest

from src.types import PolicyEvent
from src.analyzer.policy_impact import map_impacts


FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "policy_events_golden.json"
)

# Ticker context covering every ticker any fixture case expects.
# Compressed shape matches what `prefilter_candidates` reads from
# config/ticker_policy_context.yaml.
GOLDEN_TICKER_CTX: dict[str, dict] = {
    "NVDA": {"sector": "semiconductor", "business": "AI GPU leader",
             "exposure": ["export_control_china", "ai_data_center"], "china_revenue_pct": 17},
    "AMD":  {"sector": "semiconductor", "business": "x86 + GPU + AI accelerator",
             "exposure": ["export_control_china", "ai_data_center"], "china_revenue_pct": 15},
    "INTC": {"sector": "semiconductor", "business": "US foundry + CPU",
             "exposure": ["chips_act_subsidy", "us_manufacturing"], "china_revenue_pct": 27},
    "TSM":  {"sector": "semiconductor", "business": "Foundry leader",
             "exposure": ["chips_act_subsidy", "taiwan_geopolitics"], "china_revenue_pct": 10},
    "MU":   {"sector": "semiconductor", "business": "Memory (DRAM/NAND)",
             "exposure": ["chips_act_subsidy", "memory_cycle"], "china_revenue_pct": 11},
    "AAPL": {"sector": "consumer_electronics", "business": "iPhone + services",
             "exposure": ["china_supply_chain", "import_tariff_china"], "china_revenue_pct": 19},
    "ENPH": {"sector": "renewable_energy", "business": "Solar microinverters",
             "exposure": ["ira_solar_credit", "us_solar_demand"], "china_revenue_pct": 0},
    "FSLR": {"sector": "renewable_energy", "business": "Utility-scale solar modules",
             "exposure": ["ira_solar_credit", "domestic_module_45x"], "china_revenue_pct": 0},
    "TSLA": {"sector": "auto_ev", "business": "EV maker + energy",
             "exposure": ["ev_tax_credit_30d", "ira_battery_sourcing"], "china_revenue_pct": 22},
    "BIIB": {"sector": "biotech", "business": "Alzheimer's neurology",
             "exposure": ["fda_alzheimer_approval", "medicare_coverage"], "china_revenue_pct": 0},
    "PFE":  {"sector": "biotech", "business": "Large pharma",
             "exposure": ["fda_label_change", "jak_inhibitor_safety"], "china_revenue_pct": 5},
    "GOOGL": {"sector": "internet", "business": "Search + ads + cloud",
              "exposure": ["antitrust_search", "regulatory_breakup_risk"], "china_revenue_pct": 0},
    "META": {"sector": "internet", "business": "Social + ads",
             "exposure": ["antitrust_platform", "regulatory_oversight"], "china_revenue_pct": 0},
    "LMT":  {"sector": "defense", "business": "Missiles, F-35, space",
             "exposure": ["us_defense_budget", "indo_pacific_demand"], "china_revenue_pct": 0},
    "RTX":  {"sector": "defense", "business": "Aerospace + missiles",
             "exposure": ["us_defense_budget", "missile_defense"], "china_revenue_pct": 0},
    "NOC":  {"sector": "defense", "business": "B-21 + space + cyber",
             "exposure": ["us_defense_budget", "strategic_systems"], "china_revenue_pct": 0},
    "XOM":  {"sector": "oil_gas", "business": "Integrated oil major",
             "exposure": ["oil_price", "spr_release"], "china_revenue_pct": 0},
    "CVX":  {"sector": "oil_gas", "business": "Integrated oil major",
             "exposure": ["oil_price", "spr_release"], "china_revenue_pct": 0},
    "JPM":  {"sector": "banks", "business": "Largest US bank",
             "exposure": ["basel_iii_endgame", "capital_rules"], "china_revenue_pct": 0},
    "BAC":  {"sector": "banks", "business": "Universal bank",
             "exposure": ["basel_iii_endgame", "capital_rules"], "china_revenue_pct": 0},
}

CATEGORY_TO_SECTORS: dict[str, list[str]] = {
    "chips_act":      ["semiconductor"],
    "export_control": ["semiconductor"],
    "tariff":         ["consumer_electronics", "semiconductor"],
    "ira":            ["renewable_energy", "auto_ev"],
    "fda":            ["biotech"],
    "antitrust":      ["internet"],
    "defense":        ["defense"],
    "energy":         ["oil_gas"],
    "interest_rate":  ["consumer_electronics", "auto_ev", "internet", "biotech"],
    "banking":        ["banks"],
}


def _live_mode() -> bool:
    if os.environ.get("POLICY_GOLDEN_OFFLINE"):
        return False
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    return True


@unittest.skipUnless(
    _live_mode(),
    "live LLM run only; set OPENAI_API_KEY and unset POLICY_GOLDEN_OFFLINE",
)
class TestPolicyGolden(unittest.TestCase):
    def test_top_impact_accuracy_at_least_80pct(self):
        with open(FIXTURE, encoding="utf-8") as f:
            cases = json.load(f)

        hits = 0
        total = 0

        for case in cases:
            events = [PolicyEvent(**e) for e in case["events"]]
            report = map_impacts(
                events=events,
                ticker_ctx=GOLDEN_TICKER_CTX,
                category_to_sectors=CATEGORY_TO_SECTORS,
                model_profile="deep",
                today=events[0].published_at[:10],
            )

            # Positive expected → score should be > 0.1
            for t in case["expected_top_positive"]:
                total += 1
                score = report.tailwind_scores.get(t, 0.0)
                if score > 0.1:
                    hits += 1

            # Negative expected → score should be < -0.1
            for t in case["expected_top_negative"]:
                total += 1
                score = report.tailwind_scores.get(t, 0.0)
                if score < -0.1:
                    hits += 1

        self.assertGreater(total, 0, "fixture must declare expectations")
        accuracy = hits / total
        self.assertGreaterEqual(
            accuracy,
            0.8,
            f"golden accuracy {hits}/{total} = {accuracy:.2%} (target ≥ 80%)",
        )


if __name__ == "__main__":
    unittest.main()
