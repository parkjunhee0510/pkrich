from __future__ import annotations

import unittest

from src.utils.earnings_pattern import build_earnings_pattern


class EarningsPatternTests(unittest.TestCase):
    def test_counts_three_quarter_beat_streak(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"quarter": "2025-Q4", "beat_miss": "beat", "surprise_pct": "+7.0%"},
                {"quarter": "2025-Q3", "beat_miss": "beat", "surprise_pct": "+5.0%"},
                {"quarter": "2025-Q2", "beat_miss": "beat", "surprise_pct": "+3.0%"},
                {"quarter": "2025-Q1", "beat_miss": "miss", "surprise_pct": "-2.0%"},
            ]
        )
        self.assertEqual(pattern["beat_streak"], 3)

    def test_inline_breaks_beat_streak(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"quarter": "2025-Q4", "beat_miss": "beat", "surprise_pct": "+4.0%"},
                {"quarter": "2025-Q3", "beat_miss": "in-line", "surprise_pct": "+0.2%"},
                {"quarter": "2025-Q2", "beat_miss": "beat", "surprise_pct": "+3.0%"},
            ]
        )
        self.assertEqual(pattern["beat_streak"], 1)

    def test_average_surprise_is_formatted(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"surprise_pct": "+6.0%"},
                {"surprise_pct": "+2.0%"},
                {"surprise_pct": "-4.0%"},
                {"surprise_pct": "+2.0%"},
            ]
        )
        self.assertEqual(pattern["avg_surprise_pct"], "+1.5%")

    def test_classifies_improving_trend(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"surprise_pct": "+6.0%"},
                {"surprise_pct": "+4.0%"},
                {"surprise_pct": "+2.0%"},
                {"surprise_pct": "0.0%"},
            ]
        )
        self.assertEqual(pattern["surprise_trend"], "improving")

    def test_classifies_deteriorating_trend(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"surprise_pct": "-4.0%"},
                {"surprise_pct": "-1.0%"},
                {"surprise_pct": "+1.0%"},
                {"surprise_pct": "+4.0%"},
            ]
        )
        self.assertEqual(pattern["surprise_trend"], "deteriorating")

    def test_classifies_stable_trend(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"surprise_pct": "+2.1%"},
                {"surprise_pct": "+1.8%"},
                {"surprise_pct": "+2.0%"},
                {"surprise_pct": "+1.9%"},
            ]
        )
        self.assertEqual(pattern["surprise_trend"], "stable")

    def test_returns_insufficient_data_for_two_points(self) -> None:
        pattern = build_earnings_pattern(
            [
                {"surprise_pct": "+3.0%"},
                {"surprise_pct": "+1.0%"},
            ]
        )
        self.assertEqual(pattern["surprise_trend"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
