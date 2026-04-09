from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.research_note import _build_ticker_context, _build_user_prompt


class ResearchNotePromptTests(unittest.TestCase):
    def test_build_ticker_context_includes_price_action_and_positioning_blocks(self) -> None:
        context = _build_ticker_context(
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "sector": "Technology",
                "price": 258.90,
                "change_percent": "+1.20%",
                "currency": "USD",
                "eps": "6.10",
                "forward_eps": "6.80",
                "earnings_growth": "+12.40% YoY",
                "sma_50": "260.57",
                "sma_200": "230.50",
                "week52_high": "288.62",
                "week52_low": "169.21",
                "price_change_7d": "+2.3%",
                "price_action": {
                    "price_change_30d": "+5.1%",
                    "atr_14d": "5.23",
                    "atr_percent": "2.02%",
                    "relative_volume": "1.42x",
                    "gap_percent": "+0.80%",
                    "price_vs_sma50": "+3.20%",
                    "price_vs_sma200": "+8.10%",
                    "week52_position": "73%",
                    "rs_vs_spy": "+4.10%",
                },
                "positioning": {
                    "short_float_pct": "3.20%",
                    "short_ratio": "2.10일",
                    "analyst_target_price": "130.00 USD",
                    "analyst_recommendation": "Buy",
                    "analyst_count": "18명",
                    "held_by_insiders": "0.07%",
                    "held_by_institutions": "61.30%",
                    "implied_volatility": "28.40%",
                },
                "upcoming_events": [
                    {"type": "earnings", "label": "실적 발표", "date": "2026-04-30", "days_until": "21"}
                ],
            }
        )

        self.assertIn("[Price Action]", context)
        self.assertIn("ATR(14): 5.23 (2.02%)", context)
        self.assertIn("[Key Levels]", context)
        self.assertIn("SMA50: 260.57 USD", context)
        self.assertIn("SMA200: 230.50 USD", context)
        self.assertIn("[Price]", context)
        self.assertIn("7D: +2.3%", context)
        self.assertIn("[Positioning]", context)
        self.assertIn("Short Float: 3.20%", context)
        self.assertIn("Next Earnings: 2026-04-30 실적 발표 (D-21)", context)

    def test_build_user_prompt_contains_trader_specific_instructions(self) -> None:
        prompt = _build_user_prompt(
            [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "sector": "Technology",
                    "eps": "6.10",
                    "forward_eps": "6.80",
                    "earnings_growth": "+12.40% YoY",
                    "price_action": {},
                    "positioning": {},
                    "upcoming_events": [],
                    "news": [],
                }
            ],
            date(2026, 4, 9),
        )

        self.assertIn('signal_or_takeaway: One sentence in Korean:', prompt)
        self.assertIn('invalidation_price: Use [Key Levels] SMA50 price from data', prompt)
        self.assertIn('Compact context:', prompt)
        self.assertIn('Structured input JSON:', prompt)
        self.assertIn('## Field Requirements', prompt)


if __name__ == "__main__":
    unittest.main()
