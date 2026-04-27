import unittest
from unittest.mock import patch

from src.types import PolicyEvent, TickerImpact
from src.analyzer.policy_impact import (
    aggregate_tailwind,
    map_impacts,
    normalize_score,
    prefilter_candidates,
)


def _evt(category="export_control", eid="evt1"):
    return PolicyEvent(
        id=eid, category=category, headline="h", summary="s",
        raw_excerpt="r", source_url="https://x", source_domain="x",
        published_at="2026-04-27T00:00:00Z", confidence=0.9,
    )


class TestPrefilter(unittest.TestCase):
    def test_keeps_only_relevant_sectors(self):
        ticker_ctx = {
            "NVDA": {"sector": "semiconductor"},
            "JNJ":  {"sector": "healthcare"},
        }
        cat_to_sec = {"export_control": ["semiconductor"]}
        out = prefilter_candidates([_evt()], ticker_ctx, cat_to_sec)
        self.assertEqual(out, {"evt1": ["NVDA"]})

    def test_unknown_category_keeps_all_tickers(self):
        ticker_ctx = {"AAA": {"sector": "x"}, "BBB": {"sector": "y"}}
        out = prefilter_candidates([_evt(category="other")], ticker_ctx, {})
        self.assertEqual(set(out["evt1"]), {"AAA", "BBB"})


class TestNormalize(unittest.TestCase):
    def test_direct_score_clamped_into_band(self):
        self.assertEqual(normalize_score("negative", "direct", 1.5), -1.0)
        self.assertEqual(normalize_score("negative", "direct", 0.2), -0.7)
        self.assertEqual(normalize_score("positive", "indirect", 0.9), 0.5)
        self.assertEqual(normalize_score("positive", "indirect", 0.1), 0.3)

    def test_neutral_zero(self):
        self.assertEqual(normalize_score("neutral", "neutral", 0.99), 0.0)
        self.assertEqual(normalize_score("negative", "neutral", 0.99), 0.0)
        self.assertEqual(normalize_score("neutral", "direct", 0.99), 0.0)


class TestAggregate(unittest.TestCase):
    def test_low_confidence_excluded_and_clipped(self):
        impacts = [
            TickerImpact("NVDA", "negative", "direct", -0.9, 0.9, "r1"),
            TickerImpact("NVDA", "negative", "indirect", -0.4, 0.4, "lowconf"),
            TickerImpact("NVDA", "negative", "indirect", -0.5, 0.8, "r3"),
        ]
        expected = max(-1.0, -0.9 * 0.9 + -0.5 * 0.8)
        self.assertAlmostEqual(
            aggregate_tailwind({"NVDA": impacts})["NVDA"],
            expected, places=3,
        )

    def test_clip_to_negative_one(self):
        impacts = [
            TickerImpact("X", "negative", "direct", -1.0, 1.0, "r1"),
            TickerImpact("X", "negative", "direct", -1.0, 1.0, "r2"),
        ]
        self.assertEqual(aggregate_tailwind({"X": impacts})["X"], -1.0)


class TestMap(unittest.TestCase):
    @patch("src.analyzer.policy_impact._openai_map")
    def test_map_chunks_large_candidate_lists(self, mock_map):
        mock_map.return_value = {"evt1": []}
        ticker_ctx = {
            f"T{i}": {
                "sector": "semiconductor",
                "business": "x",
                "exposure": [],
                "china_revenue_pct": 0,
            }
            for i in range(60)
        }
        report = map_impacts(
            events=[_evt()],
            ticker_ctx=ticker_ctx,
            category_to_sectors={"export_control": ["semiconductor"]},
            chunk_size=25,
            model_profile="deep",
        )
        # 60 candidates → 3 chunks
        self.assertEqual(mock_map.call_count, 3)
        self.assertIn("evt1", report.impacts_by_event)

    @patch("src.analyzer.policy_impact._openai_map")
    def test_chunk_failure_does_not_kill_others(self, mock_map):
        # First chunk raises, second returns a hit on T35 (which lands in
        # chunk 2 under alphabetical sort: T31..T39 are at indices 25..33).
        mock_map.side_effect = [
            RuntimeError("boom"),
            {"evt1": [{"ticker": "T35", "direction": "negative",
                       "strength": "direct", "score": 0.9,
                       "confidence": 0.9, "rationale": "exposure"}]},
            {"evt1": []},
        ]
        ticker_ctx = {
            f"T{i}": {
                "sector": "semiconductor",
                "business": "x",
                "exposure": [],
                "china_revenue_pct": 0,
            }
            for i in range(60)
        }
        report = map_impacts(
            events=[_evt()],
            ticker_ctx=ticker_ctx,
            category_to_sectors={"export_control": ["semiconductor"]},
            chunk_size=25,
            model_profile="deep",
        )
        self.assertIn("T35", report.tailwind_scores)
        self.assertLess(report.tailwind_scores["T35"], 0)
        self.assertEqual(report.metadata["chunks_failed"], 1)

    @patch("src.analyzer.policy_impact._openai_map")
    def test_hallucinated_ticker_dropped(self, mock_map):
        mock_map.return_value = {
            "evt1": [{"ticker": "FAKE_TICKER", "direction": "negative",
                      "strength": "direct", "score": 0.9,
                      "confidence": 0.9, "rationale": "x"}]
        }
        ticker_ctx = {"NVDA": {"sector": "semiconductor", "business": "x",
                               "exposure": [], "china_revenue_pct": 0}}
        report = map_impacts(
            events=[_evt()],
            ticker_ctx=ticker_ctx,
            category_to_sectors={"export_control": ["semiconductor"]},
            chunk_size=25,
            model_profile="deep",
        )
        self.assertNotIn("FAKE_TICKER", report.tailwind_scores)


if __name__ == "__main__":
    unittest.main()
