from __future__ import annotations

import unittest

from src.types import NewsItem, TickerAnalysis
from src.utils.news_tone import build_news_tone


class NewsToneTests(unittest.TestCase):
    def test_build_news_tone_returns_bullish(self) -> None:
        analysis = TickerAnalysis(
            ticker='AAPL',
            name='Apple Inc.',
            date='2026-04-08',
            summary='summary',
            key_news=['실적 호조와 수요 성장 기대'],
            news_references=[NewsItem(title='Apple earnings beat and demand outlook improves', source='Reuters')],
            financial_highlights=[],
            risks_or_watchpoints=[],
            signal_or_takeaway='watch',
            data_snapshot={},
        )

        tone = build_news_tone(analysis)

        self.assertEqual(tone['label'], 'bullish')
        self.assertGreater(float(tone['score']), 0)

    def test_build_news_tone_returns_bearish(self) -> None:
        analysis = TickerAnalysis(
            ticker='AAPL',
            name='Apple Inc.',
            date='2026-04-08',
            summary='summary',
            key_news=['가이던스 하향과 소송 리스크'],
            news_references=[NewsItem(title='Apple downgrade as weak outlook and lawsuit concerns rise', source='Reuters')],
            financial_highlights=[],
            risks_or_watchpoints=[],
            signal_or_takeaway='watch',
            data_snapshot={},
        )

        tone = build_news_tone(analysis)

        self.assertEqual(tone['label'], 'bearish')
        self.assertLess(float(tone['score']), 0)


if __name__ == '__main__':
    unittest.main()
