import unittest
from unittest.mock import patch

from src.decision.search_quality import (
    attach_search_quality_shadow,
    calculate_search_evidence_score,
)
from src.types import TickerDecision


def _search_payload(ticker: str, summary: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "date": "2026-05-07",
        "provider": "cache",
        "items": [],
        "by_ticker": {ticker: summary},
        "run_summary": {},
    }


class SearchQualityGateTests(unittest.TestCase):
    def test_calculates_score_from_coverage_freshness_relevance_and_diversity(self) -> None:
        score = calculate_search_evidence_score(
            {
                "coverage_score": 0.7,
                "freshness_score": 0.8,
                "average_relevance_score": 0.9,
                "source_diversity": 3,
                "evidence_count": 4,
            }
        )

        self.assertEqual(score, 0.81)

    def test_weak_search_evidence_shadow_gate_does_not_change_buy_action(self) -> None:
        decision = TickerDecision(
            ticker="ALAB",
            action="buy",
            conviction=72,
            reason="strong growth",
            confidence_meta={"data_quality_score": 0.82},
        )
        payload = _search_payload(
            "ALAB",
            {
                "coverage_score": 0.2,
                "freshness_score": 0.2,
                "average_relevance_score": 0.5,
                "source_diversity": 1,
                "evidence_count": 1,
            },
        )

        [enriched] = attach_search_quality_shadow([decision], payload)

        self.assertEqual(enriched.action, "buy")
        self.assertEqual(enriched.confidence_meta["data_quality_score"], 0.82)
        self.assertLess(enriched.confidence_meta["search_evidence_score"], 0.55)
        self.assertEqual(enriched.confidence_meta["search_quality_gate"]["mode"], "shadow")
        self.assertTrue(enriched.confidence_meta["search_quality_gate"]["would_cap_action"])
        self.assertEqual(
            enriched.confidence_meta["search_quality_gate"]["max_action_if_enforced"],
            "watch",
        )

    def test_enforced_search_quality_gate_caps_weak_buy_to_watch(self) -> None:
        decision = TickerDecision(
            ticker="ALAB",
            action="buy",
            conviction=72,
            reason="strong growth",
        )
        payload = _search_payload(
            "ALAB",
            {
                "coverage_score": 0.2,
                "freshness_score": 0.2,
                "average_relevance_score": 0.5,
                "source_diversity": 1,
                "evidence_count": 1,
            },
        )

        with patch.dict("os.environ", {"DECISION_SEARCH_QUALITY_GATE_MODE": "enforce"}):
            [enriched] = attach_search_quality_shadow([decision], payload)

        gate = enriched.confidence_meta["search_quality_gate"]
        self.assertEqual(enriched.action, "watch")
        self.assertEqual(gate["mode"], "enforce")
        self.assertTrue(gate["would_cap_action"])
        self.assertTrue(gate["enforced"])
        self.assertEqual(gate["original_action"], "buy")
        self.assertEqual(gate["capped_action"], "watch")
        self.assertIn("검색 근거 품질 게이트 적용", enriched.reason)

    def test_enforced_search_quality_gate_does_not_cap_unavailable_payload(self) -> None:
        decision = TickerDecision(ticker="MOD", action="buy", conviction=68, reason="setup")

        with patch.dict("os.environ", {"DECISION_SEARCH_QUALITY_GATE_MODE": "enforce"}):
            [enriched] = attach_search_quality_shadow([decision], None)

        gate = enriched.confidence_meta["search_quality_gate"]
        self.assertEqual(enriched.action, "buy")
        self.assertEqual(gate["mode"], "enforce")
        self.assertEqual(gate["reason"], "search_evidence_unavailable")
        self.assertFalse(gate["would_cap_action"])
        self.assertFalse(gate["enforced"])

    def test_weak_search_evidence_does_not_cap_non_buy_actions(self) -> None:
        decision = TickerDecision(
            ticker="COHR",
            action="watch",
            conviction=61,
            reason="watch setup",
        )
        payload = _search_payload(
            "COHR",
            {
                "coverage_score": 0.0,
                "freshness_score": 0.0,
                "average_relevance_score": 0.0,
                "source_diversity": 0,
                "evidence_count": 0,
            },
        )

        [enriched] = attach_search_quality_shadow([decision], payload)

        self.assertEqual(enriched.action, "watch")
        self.assertEqual(enriched.confidence_meta["search_evidence_score"], 0.0)
        self.assertFalse(enriched.confidence_meta["search_quality_gate"]["would_cap_action"])

    def test_unavailable_search_payload_records_no_shadow_penalty(self) -> None:
        decision = TickerDecision(ticker="MOD", action="buy", conviction=68, reason="setup")

        [enriched] = attach_search_quality_shadow([decision], None)

        self.assertEqual(enriched.action, "buy")
        self.assertIsNone(enriched.confidence_meta["search_evidence_score"])
        self.assertEqual(
            enriched.confidence_meta["search_quality_gate"]["reason"],
            "search_evidence_unavailable",
        )
        self.assertFalse(enriched.confidence_meta["search_quality_gate"]["would_cap_action"])


if __name__ == "__main__":
    unittest.main()
