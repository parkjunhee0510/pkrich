from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.research_note import _analyze_batches_with_client
from src.types import CollectedTickerData, NewsItem, WatchlistItem


def _watchlist_items() -> list[WatchlistItem]:
    return [
        WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology'),
        WatchlistItem(ticker='MSFT', name='Microsoft Corporation', sector='Technology'),
        WatchlistItem(ticker='NVDA', name='NVIDIA Corporation', sector='Semiconductors'),
        WatchlistItem(ticker='AMZN', name='Amazon.com, Inc.', sector='Consumer Discretionary'),
        WatchlistItem(ticker='GOOGL', name='Alphabet Inc.', sector='Communication Services'),
        WatchlistItem(ticker='TSLA', name='Tesla, Inc.', sector='Consumer Discretionary'),
    ]


def _collected_data(watchlist: list[WatchlistItem]) -> dict[str, CollectedTickerData]:
    return {
        item.ticker: CollectedTickerData(
            ticker=item.ticker,
            name=item.name,
            sector=item.sector,
            price=100.0,
            change_percent=1.5,
            currency='USD',
            market_cap='1.00T',
            pe_ratio='25.0',
            summary_note='요약 메모',
            eps='5.00',
            week52_high='120.0',
            week52_low='80.0',
            sma_50='95.0',
            sma_200='90.0',
        )
        for item in watchlist
    }


def _news_map(watchlist: list[WatchlistItem]) -> dict[str, list[NewsItem]]:
    return {item.ticker: [NewsItem(title=f'{item.ticker} headline', source='Reuters')] for item in watchlist}


def _openai_entry(ticker: str) -> dict[str, object]:
    return {
        'ticker': ticker,
        'summary': f'{ticker} 요약',
        'key_news': [f'{ticker} 뉴스'],
        'financial_highlights': [f'{ticker} 재무'],
        'risks_or_watchpoints': [f'{ticker} 리스크'],
        'signal_or_takeaway': f'{ticker} 결론',
    }


class AnalyzerBatchingTests(unittest.TestCase):
    def test_analyze_batches_uses_fallback_only_for_failed_batch(self) -> None:
        watchlist = _watchlist_items()
        collected = _collected_data(watchlist)
        news_map = _news_map(watchlist)
        first_batch = [_openai_entry(item.ticker) for item in watchlist[:5]]

        def side_effect(*args, **kwargs):
            batch = args[3]
            return first_batch if len(batch) == 5 else None

        with patch.dict(os.environ, {'BATCH_SIZE': '5'}, clear=False):
            with patch('src.analyzer.research_note._call_openai_batch', side_effect=side_effect):
                analyses = _analyze_batches_with_client(
                    object(),
                    'gpt-5.4-mini',
                    watchlist,
                    collected,
                    news_map,
                    date(2026, 4, 8),
                )

        self.assertEqual(len(analyses), 6)
        self.assertEqual(analyses[0].summary, 'AAPL 요약')
        self.assertEqual(analyses[4].signal_or_takeaway, 'GOOGL 결론')
        self.assertIn('Tesla, Inc.(TSLA)', analyses[5].summary)

    def test_analyze_batches_falls_back_for_missing_ticker_in_successful_batch(self) -> None:
        watchlist = _watchlist_items()[:2]
        collected = _collected_data(watchlist)
        news_map = _news_map(watchlist)

        with patch.dict(os.environ, {'BATCH_SIZE': '2'}, clear=False):
            with patch('src.analyzer.research_note._call_openai_batch', return_value=[_openai_entry('AAPL')]):
                analyses = _analyze_batches_with_client(
                    object(),
                    'gpt-5.4-mini',
                    watchlist,
                    collected,
                    news_map,
                    date(2026, 4, 8),
                )

        self.assertEqual(analyses[0].summary, 'AAPL 요약')
        self.assertIn('Microsoft Corporation(MSFT)', analyses[1].summary)

    def test_analyze_batches_falls_back_for_all_batches_when_requests_fail(self) -> None:
        watchlist = _watchlist_items()
        collected = _collected_data(watchlist)
        news_map = _news_map(watchlist)

        with patch.dict(os.environ, {'BATCH_SIZE': '1'}, clear=False):
            with patch('src.analyzer.research_note._call_openai_batch', return_value=None):
                analyses = _analyze_batches_with_client(
                    object(),
                    'gpt-5.4-mini',
                    watchlist,
                    collected,
                    news_map,
                    date(2026, 4, 8),
                )

        self.assertEqual(len(analyses), 6)
        self.assertTrue(all('는 ' in analysis.summary for analysis in analyses))


if __name__ == '__main__':
    unittest.main()
