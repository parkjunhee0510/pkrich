from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.research_note import _build_system_prompt, _build_ticker_context, _build_user_prompt


class ResearchNotePromptTests(unittest.TestCase):
    def test_build_ticker_context_includes_price_action_and_positioning_blocks(self) -> None:
        context = _build_ticker_context(
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'sector': 'Technology',
                'price': 258.90,
                'change_percent': '+1.20',
                'currency': 'USD',
                'eps': '7.90',
                'forward_eps': '9.33',
                'earnings_growth': '+18.30% YoY',
                'sma_50': '260.57',
                'sma_200': '230.50',
                'week52_high': '288.62',
                'week52_low': '169.21',
                'price_change_7d': '+2.30%',
                'price_action': {
                    'price_change_30d': '-0.74%',
                    'atr_14d': '6.06',
                    'atr_percent': '2.34%',
                    'relative_volume': '1.16x',
                    'gap_percent': '+0.25%',
                    'price_vs_sma50': '-0.64%',
                    'price_vs_sma200': '+12.34%',
                    'week52_position': '75%',
                    'rs_vs_spy': '+1.10%',
                },
                'positioning': {
                    'short_float_pct': '0.84%',
                    'short_ratio': '1.75일',
                    'analyst_target_price': '295.32 USD',
                    'analyst_recommendation': 'Strong Buy',
                    'analyst_count': '42명',
                    'held_by_insiders': '0.05%',
                    'held_by_institutions': '63.40%',
                    'implied_volatility': '28.40%',
                },
                'upcoming_events': [
                    {'type': 'earnings', 'label': '실적 발표', 'date': '2026-04-30', 'days_until': '21'}
                ],
            }
        )

        self.assertIn('[Price Action]', context)
        self.assertIn('ATR(14): 6.06 (2.34%)', context)
        self.assertIn('[Key Levels]', context)
        self.assertIn('SMA50: 260.57 USD', context)
        self.assertIn('SMA200: 230.50 USD', context)
        self.assertIn('[Price]', context)
        self.assertIn('7D: +2.30%', context)
        self.assertIn('[Positioning]', context)
        self.assertIn('Short Float: 0.84%', context)
        self.assertIn('Next Earnings: 2026-04-30 실적 발표 (D-21)', context)

    def test_build_user_prompt_contains_trader_specific_instructions(self) -> None:
        prompt = _build_user_prompt(
            [
                {
                    'ticker': 'AAPL',
                    'name': 'Apple Inc.',
                    'sector': 'Technology',
                    'eps': '7.90',
                    'forward_eps': '9.33',
                    'earnings_growth': '+18.30% YoY',
                    'price_action': {},
                    'positioning': {},
                    'upcoming_events': [],
                    'news': [],
                }
            ],
            date(2026, 4, 9),
        )

        self.assertIn('signal_or_takeaway: One structured sentence in Korean:', prompt)
        self.assertIn('invalidation_price: Same as stop_loss but with context', prompt)
        self.assertIn('Compact context:', prompt)
        self.assertIn('Structured input JSON:', prompt)
        self.assertIn('## Field Requirements', prompt)

    def test_build_system_prompt_contains_na_avoidance_rule(self) -> None:
        prompt = _build_system_prompt()

        self.assertIn('If any input field is "N/A" or missing, do not repeat it.', prompt)


if __name__ == '__main__':
    unittest.main()
