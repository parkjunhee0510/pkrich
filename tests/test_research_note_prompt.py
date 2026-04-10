from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.research_note import _build_payload, _build_system_prompt, _build_ticker_context, _build_user_prompt
from src.types import CollectedTickerData, NewsItem, WatchlistItem


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
                'quarterly_financials': [
                    {'quarter': '2025-Q4', 'eps': '2.10', 'estimated_eps': '2.00', 'beat_miss': 'beat', 'surprise_pct': '+5.00%'}
                ],
                'signal_history': [
                    {'signal_date': '2026-04-03', 'signal_direction': 'bull', 'return_5d': '+2.30%', 'catalyst_tag': '실적'}
                ],
                'sector_peer_context': {
                    'sector': 'Technology',
                    'peer_count': '2',
                    'average_pe': '22.40x',
                    'average_price_change_30d': '+4.10%',
                    'average_rs_vs_spy': '+2.20%',
                    'ticker_pe': '25.00',
                    'ticker_price_change_30d': '-0.74%',
                    'ticker_rs_vs_spy': '+1.10%',
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
        self.assertIn('[Earnings History]', context)
        self.assertIn('2025-Q4: EPS 2.10 vs est 2.00 (beat +5.00%)', context)
        self.assertIn('[Signal History]', context)
        self.assertIn('2026-04-03 bull +2.30% (5d, 실적)', context)
        self.assertIn('[Sector Comparison]', context)
        self.assertIn('Technology peers 2개 평균: PE 22.40x', context)

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
        self.assertIn('news_tone: Return an object with label', prompt)

    def test_build_system_prompt_contains_na_avoidance_rule(self) -> None:
        prompt = _build_system_prompt()

        self.assertIn('If any input field is "N/A" or missing, do not repeat it.', prompt)
        self.assertIn('Reflect earnings surprise patterns', prompt)
        self.assertIn('Reference example JSON structure', prompt)

    def test_build_payload_includes_signal_history_peer_context_and_deduped_news(self) -> None:
        watchlist = [
            WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology'),
            WatchlistItem(ticker='MSFT', name='Microsoft Corporation', sector='Technology'),
        ]
        collected = {
            'AAPL': CollectedTickerData(
                ticker='AAPL',
                name='Apple Inc.',
                sector='Technology',
                price=100.0,
                change_percent=1.0,
                currency='USD',
                market_cap='1.00T',
                pe_ratio='25.0',
                summary_note='memo',
                price_change_30d='+6.00%',
                rs_vs_spy='+3.00%',
                quarterly_financials=[{'quarter': '2025-Q4'}],
            ),
            'MSFT': CollectedTickerData(
                ticker='MSFT',
                name='Microsoft Corporation',
                sector='Technology',
                price=110.0,
                change_percent=1.2,
                currency='USD',
                market_cap='1.50T',
                pe_ratio='20.0',
                summary_note='memo',
                price_change_30d='+2.00%',
                rs_vs_spy='+1.00%',
            ),
        }
        news_map = {
            'AAPL': [
                NewsItem(title='Apple earnings beat expectations', source='Reuters', published_at='2026-04-09'),
                NewsItem(title='Apple earnings beat expectations on iPhone demand', source='Yahoo Finance', published_at='2026-04-09'),
            ],
            'MSFT': [NewsItem(title='Microsoft cloud demand improves', source='Reuters', published_at='2026-04-09')],
        }
        payload = _build_payload(
            watchlist,
            collected,
            news_map,
            signal_history_map={'AAPL': [{'signal_date': '2026-04-03', 'signal_direction': 'bull', 'return_5d': '+2.30%'}]},
        )

        self.assertEqual(payload[0]['quarterly_financials'], [{'quarter': '2025-Q4'}])
        self.assertEqual(payload[0]['signal_history'][0]['signal_date'], '2026-04-03')
        self.assertEqual(payload[0]['sector_peer_context']['average_pe'], '20.00x')
        self.assertEqual(len(payload[0]['news']), 1)


if __name__ == '__main__':
    unittest.main()
