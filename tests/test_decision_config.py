from __future__ import annotations

import unittest

from src.decision.config import multiplier_for, normalize_decision_config


class DecisionConfigTests(unittest.TestCase):
    def test_aliases_are_normalized_to_canonical_factor_names(self) -> None:
        normalized = normalize_decision_config(
            {
                "factors": {"valuation": {"max": 20}},
                "regime_multipliers": {
                    "risk_on": {"catalyst": 1.2, "signal_record": 1.1},
                    "risk_off": {"regime": 0.7, "earnings": 1.4},
                    "neutral": {},
                },
            }
        )
        self.assertIn("catalyst_recency", normalized["regime_multipliers"]["risk_on"])
        self.assertIn("signal_track_record", normalized["regime_multipliers"]["risk_on"])
        self.assertIn("regime_adjustment", normalized["regime_multipliers"]["risk_off"])
        self.assertIn("earnings_pattern", normalized["regime_multipliers"]["risk_off"])

    def test_unknown_regime_block_fails(self) -> None:
        with self.assertRaises(ValueError):
            normalize_decision_config(
                {
                    "factors": {},
                    "regime_multipliers": {"panic": {"momentum": 1.5}},
                }
            )

    def test_default_multiplier_is_one(self) -> None:
        normalized = normalize_decision_config({"factors": {}, "regime_multipliers": {}})
        self.assertEqual(multiplier_for("momentum", "neutral", normalized["regime_multipliers"]), 1.0)

    def test_zero_multiplier_is_clamped(self) -> None:
        normalized = normalize_decision_config(
            {
                "factors": {},
                "regime_multipliers": {"risk_on": {"momentum": 0}, "risk_off": {}, "neutral": {}},
            }
        )
        self.assertEqual(multiplier_for("momentum", "risk_on", normalized["regime_multipliers"]), 0.1)


if __name__ == "__main__":
    unittest.main()
