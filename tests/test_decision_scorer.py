from __future__ import annotations

import unittest

from src.decision.base import DecisionFactor, FactorScore
from src.decision.scorer import ConvictionScorer


class _FactorA(DecisionFactor):
    name = "valuation"
    weight_range = (-10, 20)
    description = "A"

    def score(self, analysis, collected, regime, signal_stats):
        raise NotImplementedError


class _FactorB(DecisionFactor):
    name = "momentum"
    weight_range = (0, 10)
    description = "B"

    def score(self, analysis, collected, regime, signal_stats):
        raise NotImplementedError


class DecisionScorerTests(unittest.TestCase):
    def test_scorer_normalizes_from_dynamic_ranges(self) -> None:
        scorer = ConvictionScorer([_FactorA(), _FactorB()])
        conviction = scorer.calculate(
            {
                "valuation": FactorScore(value=-10, confidence=1.0, reasoning=""),
                "momentum": FactorScore(value=20, confidence=1.0, reasoning=""),
            },
            "neutral",
        )
        self.assertEqual(conviction, 50)

    def test_scorer_clamps_to_zero_and_hundred(self) -> None:
        scorer = ConvictionScorer([_FactorA(), _FactorB()])
        self.assertEqual(
            scorer.calculate(
                {
                    "valuation": FactorScore(value=-50, confidence=1.0, reasoning=""),
                    "momentum": FactorScore(value=-50, confidence=1.0, reasoning=""),
                },
                "neutral",
            ),
            0,
        )
        self.assertEqual(
            scorer.calculate(
                {
                    "valuation": FactorScore(value=50, confidence=1.0, reasoning=""),
                    "momentum": FactorScore(value=50, confidence=1.0, reasoning=""),
                },
                "neutral",
            ),
            100,
        )

    def test_risk_on_multiplier_lifts_momentum_impact(self) -> None:
        scorer = ConvictionScorer(
            [_FactorA(), _FactorB()],
            {"risk_on": {"momentum": 1.3}, "risk_off": {}, "neutral": {}},
        )
        scores = {
            "valuation": FactorScore(value=0, confidence=1.0, reasoning=""),
            "momentum": FactorScore(value=10, confidence=1.0, reasoning=""),
        }
        self.assertGreater(scorer.calculate(scores, "risk_on"), scorer.calculate(scores, "neutral"))

    def test_risk_off_multiplier_reweights_defensive_factors(self) -> None:
        scorer = ConvictionScorer(
            [_FactorA(), _FactorB()],
            {"risk_on": {}, "risk_off": {"valuation": 1.4, "momentum": 0.7}, "neutral": {}},
        )
        scores = {
            "valuation": FactorScore(value=5, confidence=1.0, reasoning=""),
            "momentum": FactorScore(value=5, confidence=1.0, reasoning=""),
        }
        self.assertNotEqual(scorer.weighted_values(scores, "risk_off"), scorer.weighted_values(scores, "neutral"))


if __name__ == "__main__":
    unittest.main()
