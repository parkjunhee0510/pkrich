import unittest

from src.output import risk_intel_config as cfg


class RiskIntelConfigTest(unittest.TestCase):
    def test_schema_and_config_versions_are_stable_strings(self) -> None:
        self.assertEqual(cfg.RISK_INTEL_SCHEMA_VERSION, "1.0.0")
        self.assertEqual(cfg.SCORING_CONFIG_VERSION, "risk-intel-scoring-v1")
        self.assertEqual(cfg.CONFIDENCE_CONFIG_VERSION, "risk-intel-confidence-v1")

    def test_trust_tier_scores_are_single_source_of_truth(self) -> None:
        self.assertEqual(cfg.TRUST_TIER_SCORES["official"], 0.90)
        self.assertEqual(cfg.TRUST_TIER_SCORES["filing"], 0.85)
        self.assertEqual(cfg.TRUST_TIER_SCORES["reputable_news"], 0.75)
        self.assertEqual(cfg.TRUST_TIER_SCORES["approved_search"], 0.65)
        self.assertEqual(cfg.TRUST_TIER_SCORES["domain_rule"], 0.45)
        self.assertEqual(cfg.TRUST_TIER_SCORES["market_data"], 0.70)
        self.assertEqual(cfg.TRUST_TIER_SCORES["social"], 0.30)
        self.assertEqual(cfg.TRUST_TIER_SCORES["low_quality"], 0.20)
        self.assertEqual(cfg.TRUST_TIER_SCORES["unknown"], 0.20)

    def test_korean_labels_cover_visible_enums(self) -> None:
        self.assertEqual(cfg.ALERT_LEVEL_LABEL_KO["observation"], "관찰")
        self.assertEqual(cfg.ALERT_LEVEL_LABEL_KO["warning"], "주의")
        self.assertEqual(cfg.ALERT_LEVEL_LABEL_KO["alert"], "경보")
        self.assertEqual(cfg.EVIDENCE_TYPE_LABEL_KO["explicit"], "명시 근거")
        self.assertEqual(cfg.EVIDENCE_TYPE_LABEL_KO["inferred"], "도메인 추론")
        self.assertEqual(cfg.EVIDENCE_TYPE_LABEL_KO["social"], "소셜 신호")
        self.assertEqual(cfg.EVIDENCE_TYPE_LABEL_KO["market"], "시장 확인")

    def test_source_type_enum_matches_graph_contract(self) -> None:
        self.assertIn("policy_document", cfg.SOURCE_TYPES)
        self.assertIn("market_reaction", cfg.SOURCE_TYPES)
        self.assertIn("social_cluster", cfg.SOURCE_TYPES)

    def test_score_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(sum(cfg.SCORE_WEIGHTS.values()), 1.0, places=6)

    def test_confidence_bands_match_spec(self) -> None:
        self.assertEqual(cfg.CONFIDENCE_BANDS["explicit"]["direct"], (0.80, 0.95))
        self.assertEqual(cfg.CONFIDENCE_BANDS["inferred"]["high"], (0.65, 0.80))
        self.assertEqual(cfg.CONFIDENCE_BANDS["market"]["moderate"], (0.45, 0.65))
        self.assertEqual(cfg.CONFIDENCE_BANDS["social"]["uncorroborated"], (0.20, 0.35))


if __name__ == "__main__":
    unittest.main()
