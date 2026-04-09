from __future__ import annotations

import unittest

from src.utils.earnings_setup import build_earnings_setup


class EarningsSetupTests(unittest.TestCase):
    def test_build_earnings_setup_formats_trader_facing_values(self) -> None:
        setup = build_earnings_setup(
            {
                "eps": "6.10",
                "forward_eps": "6.80",
                "earnings_growth": "+12.40% YoY",
            },
            [
                {
                    "quarter": "2025-Q4",
                    "estimated_eps": "2.00",
                    "surprise_pct": "+5.00%",
                    "beat_miss": "beat",
                }
            ],
            [{"type": "earnings", "label": "실적 발표", "date": "2026-04-14", "days_until": "6", "timing": "AMC"}],
            currency="USD",
        )

        self.assertEqual(setup["forward_eps"], "6.80 USD/share")
        self.assertEqual(setup["ttm_eps"], "6.10 USD/share")
        self.assertEqual(setup["forward_vs_ttm"], "+11.48%")
        self.assertEqual(setup["latest_estimated_eps"], "2.00 USD/share")
        self.assertEqual(setup["latest_surprise_pct"], "+5.00%")
        self.assertEqual(setup["latest_beat_miss"], "beat")
        self.assertEqual(setup["next_earnings_event"], "2026-04-14 실적 발표 (D-6 · AMC)")

    def test_build_earnings_setup_preserves_estimated_growth_label(self) -> None:
        setup = build_earnings_setup(
            {
                "eps": "6.10",
                "forward_eps": "6.80",
                "earnings_growth": "+8.20% YoY est",
            },
            [],
            [],
            currency="USD",
        )

        self.assertEqual(setup["earnings_growth"], "+8.20% YoY est")


if __name__ == "__main__":
    unittest.main()
