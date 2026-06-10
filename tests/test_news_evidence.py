from __future__ import annotations

import json
import unittest

from src.utils.news_evidence import build_news_evidence


class NewsEvidenceTests(unittest.TestCase):
    def test_strong_news_evidence_from_positive_tone_llm_and_catalyst(self) -> None:
        evidence = build_news_evidence(
            {
                "news_tone": "강세",
                "signal_direction": "bull",
                "llm_direction": "bull",
                "catalyst_tag": "실적",
                "factors_json": json.dumps({"catalyst_recency": 20}),
                "news_references": json.dumps(
                    [
                        {"title": "A raises guidance", "source": "Reuters"},
                        {"title": "A reports earnings", "source": "Company IR"},
                    ]
                ),
                "confidence_meta_json": json.dumps({"search_evidence_score": 0.72}),
            }
        )

        self.assertEqual(evidence["strength"], "strong")
        self.assertEqual(evidence["tone"], "bullish")
        self.assertEqual(evidence["llm_direction"], "bull")
        self.assertEqual(evidence["llm_alignment"], "aligned")
        self.assertEqual(evidence["score"], 100.0)
        self.assertEqual(evidence["source_count"], 2)
        self.assertTrue(evidence["has_recent_catalyst"])
        self.assertTrue(evidence["has_hard_catalyst"])
        self.assertIn("positive_news", evidence["reason_chips"])
        self.assertIn("llm_bull_aligned", evidence["reason_chips"])
        self.assertIn("recent_catalyst", evidence["reason_chips"])
        self.assertIn("source_coverage", evidence["reason_chips"])

    def test_bearish_news_and_llm_reduce_evidence(self) -> None:
        evidence = build_news_evidence(
            {
                "news_tone": "약세",
                "signal_direction": "bull",
                "llm_direction": "bear",
                "catalyst_tag": "",
            }
        )

        self.assertEqual(evidence["strength"], "insufficient")
        self.assertEqual(evidence["tone"], "bearish")
        self.assertEqual(evidence["llm_direction"], "bear")
        self.assertEqual(evidence["llm_alignment"], "conflict")
        self.assertEqual(evidence["score"], 0.0)
        self.assertIn("negative_news", evidence["reason_chips"])

    def test_missing_news_fields_return_insufficient_payload(self) -> None:
        evidence = build_news_evidence({})

        self.assertEqual(evidence["strength"], "insufficient")
        self.assertEqual(evidence["tone"], "neutral")
        self.assertEqual(evidence["llm_direction"], "unknown")
        self.assertEqual(evidence["llm_alignment"], "missing")
        self.assertEqual(evidence["score"], 25.0)
        self.assertEqual(evidence["source_count"], 0)
        self.assertFalse(evidence["has_recent_catalyst"])
        self.assertFalse(evidence["has_hard_catalyst"])
        self.assertIn("missing_news", evidence["reason_chips"])
        self.assertIn("insufficient", evidence["summary"].lower())

    def test_english_and_korean_labels_normalize_consistently(self) -> None:
        bullish = build_news_evidence({"news_tone": "positive", "llm_direction": "bullish"})
        korean_positive = build_news_evidence({"news_tone": "긍정적", "llm_direction": "강세"})
        bearish = build_news_evidence({"news_tone": "negative", "llm_direction": "bearish"})
        korean_negative = build_news_evidence({"news_tone": "부정", "llm_direction": "약세"})

        self.assertEqual(bullish["tone"], "bullish")
        self.assertEqual(korean_positive["tone"], "bullish")
        self.assertEqual(bearish["tone"], "bearish")
        self.assertEqual(korean_negative["tone"], "bearish")
        self.assertEqual(bullish["llm_direction"], "bull")
        self.assertEqual(korean_positive["llm_direction"], "bull")
        self.assertEqual(bearish["llm_direction"], "bear")
        self.assertEqual(korean_negative["llm_direction"], "bear")

    def test_score_is_clamped_to_zero_to_one_hundred(self) -> None:
        strong = build_news_evidence(
            {
                "news_tone": "bullish",
                "signal_direction": "bull",
                "llm_direction": "bull",
                "catalyst_tag": "earnings guidance contract policy",
                "catalyst_recency": 1000,
                "news_references": json.dumps([{}, {}, {}, {}]),
                "search_evidence_score": 1000,
            }
        )
        weak = build_news_evidence(
            {
                "news_tone": "bearish",
                "signal_direction": "bull",
                "llm_direction": "bear",
                "search_evidence_score": -1000,
            }
        )

        self.assertEqual(strong["score"], 100.0)
        self.assertEqual(weak["score"], 0.0)

    def test_empty_news_references_falls_back_to_source_titles(self) -> None:
        evidence = build_news_evidence(
            {
                "news_references": json.dumps([]),
                "key_news_source_titles": json.dumps(["A source", "B source"]),
            }
        )

        self.assertEqual(evidence["source_count"], 2)
        self.assertIn("source_coverage", evidence["reason_chips"])
        self.assertNotIn("source_limited", evidence["reason_chips"])
        self.assertNotIn("missing_news", evidence["reason_chips"])

    def test_hard_catalyst_short_terms_require_token_boundaries(self) -> None:
        interview = build_news_evidence({"catalyst_tag": "chairman interview"})
        rumor = build_news_evidence({"catalyst_tag": "third-party rumor"})
        investor_relations = build_news_evidence({"catalyst_tag": "Company IR"})
        filing = build_news_evidence({"catalyst_tag": "SEC filing"})

        self.assertFalse(interview["has_hard_catalyst"])
        self.assertFalse(rumor["has_hard_catalyst"])
        self.assertTrue(investor_relations["has_hard_catalyst"])
        self.assertTrue(filing["has_hard_catalyst"])

    def test_malformed_json_fields_are_treated_as_absent_evidence(self) -> None:
        evidence = build_news_evidence(
            {
                "factors_json": "{",
                "news_references": "{",
                "key_news_source_titles": "{",
                "confidence_meta_json": "{",
            }
        )

        self.assertEqual(evidence["strength"], "insufficient")
        self.assertEqual(evidence["score"], 25.0)
        self.assertEqual(evidence["source_count"], 0)
        self.assertEqual(evidence["catalyst_recency_score"], 0.0)
        self.assertIn("missing_news", evidence["reason_chips"])
        self.assertNotIn("search_evidence", evidence["reason_chips"])

    def test_non_finite_numeric_values_are_ignored(self) -> None:
        evidence = build_news_evidence(
            {
                "catalyst_recency": "Infinity",
                "search_evidence_score": "NaN",
                "factors_json": json.dumps({"catalyst_recency": float("inf")}),
                "confidence_meta_json": json.dumps({"search_evidence_score": float("nan")}),
            }
        )

        self.assertEqual(evidence["score"], 25.0)
        self.assertEqual(evidence["catalyst_recency_score"], 0.0)
        self.assertFalse(evidence["has_recent_catalyst"])
        self.assertNotIn("recent_catalyst", evidence["reason_chips"])
        self.assertNotIn("search_evidence", evidence["reason_chips"])
        self.assertIn("missing_news", evidence["reason_chips"])

    def test_structured_tone_and_direction_labels_are_supported(self) -> None:
        evidence = build_news_evidence(
            {
                "news_tone": {"label": "bullish", "score": 1},
                "llm_direction": {"direction": "bull"},
            }
        )

        self.assertEqual(evidence["tone"], "bullish")
        self.assertEqual(evidence["llm_direction"], "bull")


if __name__ == "__main__":
    unittest.main()
