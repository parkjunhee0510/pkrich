import unittest

from src.output.risk_intel_scoring import (
    alert_level_for_score,
    apply_caps,
    confidence_for_edge,
    evidence_strength,
    freshness_score,
    geometric_mean,
    raw_score,
)


class RiskIntelScoringTest(unittest.TestCase):
    def test_raw_score_matches_weighted_breakdown(self) -> None:
        breakdown = {
            "evidence_strength": 0.90,
            "proximity_score": 0.68,
            "exposure_score": 1.00,
            "market_confirmation_score": 0.50,
            "downside_severity_score": 0.43,
            "social_momentum_score": 0.00,
            "freshness_score": 0.92,
        }
        self.assertAlmostEqual(raw_score(breakdown), 0.7424, places=4)

    def test_cap_application_keeps_raw_and_final_distinct(self) -> None:
        result = apply_caps(0.58, ["inference_only_cap"])
        self.assertEqual(result["raw_score"], 0.58)
        self.assertEqual(result["score"], 0.49)
        self.assertEqual(result["score_kind"], "capped_final")
        self.assertEqual(result["cap_value"], 0.49)

    def test_uncapped_score_is_final(self) -> None:
        result = apply_caps(0.74, [])
        self.assertEqual(result["raw_score"], 0.74)
        self.assertEqual(result["score"], 0.74)
        self.assertEqual(result["score_kind"], "final")
        self.assertIsNone(result["cap_value"])

    def test_alert_level_uses_final_score(self) -> None:
        self.assertEqual(alert_level_for_score(0.39), "observation")
        self.assertEqual(alert_level_for_score(0.49), "warning")
        self.assertEqual(alert_level_for_score(0.70), "alert")

    def test_evidence_strength_uses_source_trust_and_bonus(self) -> None:
        records = [
            {"id": "record:official", "trust_tier": "official", "source_type": "policy_document"},
            {"id": "record:news", "trust_tier": "reputable_news", "source_type": "reputable_news"},
            {"id": "record:social", "trust_tier": "social", "source_type": "social_cluster"},
        ]
        self.assertAlmostEqual(evidence_strength(records), 0.95)

    def test_edge_confidence_uses_configured_bands(self) -> None:
        self.assertEqual(confidence_for_edge("explicit", "direct"), 0.875)
        self.assertEqual(confidence_for_edge("inferred", "medium"), 0.55)
        self.assertEqual(confidence_for_edge("market", "moderate"), 0.55)
        self.assertEqual(confidence_for_edge("social", "uncorroborated"), 0.275)

    def test_geometric_mean_and_freshness(self) -> None:
        self.assertAlmostEqual(geometric_mean([0.81, 0.64]), 0.72)
        self.assertAlmostEqual(freshness_score(age_hours=72, half_life_hours=72), 0.5)


class RiskIntelCalibrationTest(unittest.TestCase):
    def test_canonical_calibration_levels(self) -> None:
        scenarios = [
            ("export control -> semiconductor -> held NVDA", 0.74, [], "alert"),
            ("taiwan strait tension -> semiconductor/shipping/defense", 0.55, [], "warning"),
            ("port strike -> logistics/retail watchlist", 0.50, [], "warning"),
            ("rare earth restriction inference-only", 0.58, ["inference_only_cap"], "warning"),
            ("social-only spike", 0.72, ["social_only_cap"], "observation"),
            ("single low-quality source", 0.65, ["single_low_quality_source_cap"], "observation"),
        ]
        for name, raw, caps, expected in scenarios:
            with self.subTest(name=name):
                final = apply_caps(raw, caps)
                self.assertEqual(alert_level_for_score(final["score"]), expected)


if __name__ == "__main__":
    unittest.main()
