from __future__ import annotations

import sys
import types
import unittest
from datetime import date
from unittest.mock import patch

from src.collector.news_rss import _build_google_news_query, _collect_google_news_provider, _merge_news_items, collect_news_for_watchlist
from src.collector.news_search import build_news_query, search_news
from src.types import NewsItem, WatchlistItem


class NewsCollectionTests(unittest.TestCase):
    def test_merge_news_items_deduplicates_and_limits(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology', keywords=['iPhone'])
        primary = [
            NewsItem(title='Apple launches new service', source='Google News', link='https://example.com/a'),
            NewsItem(title='Apple launches new service', source='Google News', link='https://example.com/b'),
        ]
        supplemental = [
            NewsItem(title='Apple earnings beat expectations', source='Reuters', published_at='2026-04-08', link='https://example.com/c'),
            NewsItem(title='Analysts revisit Apple outlook', source='DuckDuckGo', link='https://example.com/d'),
        ]

        merged = _merge_news_items(item, primary, supplemental, max_items=2, run_date=date(2026, 4, 8))

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].title, 'Apple earnings beat expectations')
        self.assertEqual(merged[1].title, 'Analysts revisit Apple outlook')

    def test_merge_news_items_applies_exclude_keywords(self) -> None:
        item = WatchlistItem(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            keywords=['iPhone'],
            exclude_keywords=['rumor'],
        )
        primary = [NewsItem(title='Apple rumor round-up', source='Google News', link='https://example.com/a')]
        supplemental = [NewsItem(title='Apple earnings preview', source='Reuters', link='https://example.com/b')]

        merged = _merge_news_items(item, primary, supplemental, max_items=5, run_date=date(2026, 4, 8))

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].title, 'Apple earnings preview')

    def test_merge_news_items_drops_entries_without_title_and_link(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology', keywords=['iPhone'])
        primary = [
            NewsItem(title='   ', source='Google News', link=''),
            NewsItem(title='Apple earnings preview', source='Reuters', link='https://example.com/a'),
        ]

        merged = _merge_news_items(item, primary, [], max_items=5, run_date=date(2026, 4, 8))

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].title, 'Apple earnings preview')

    def test_merge_news_items_prefers_recent_articles_over_stale_results(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology', keywords=['iPhone'])
        primary = [
            NewsItem(
                title='Apple older Reuters feature',
                source='Reuters',
                published_at='2025-01-30',
                link='https://example.com/old-reuters',
            ),
            NewsItem(
                title='Apple current earnings update',
                source='Reuters',
                published_at='2026-04-08',
                link='https://example.com/current-reuters',
            ),
            NewsItem(
                title='Apple new product preview',
                source='Yahoo Finance',
                published_at='2026-04-07',
                link='https://example.com/current-yahoo',
            ),
            NewsItem(
                title='Apple supply chain note',
                source='Google News',
                published_at='2026-04-06',
                link='https://example.com/current-google',
            ),
        ]

        merged = _merge_news_items(item, primary, [], max_items=5, run_date=date(2026, 4, 8))

        self.assertEqual([entry.title for entry in merged], [
            'Apple current earnings update',
            'Apple new product preview',
            'Apple supply chain note',
        ])

    def test_merge_news_items_limits_same_source_concentration(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology', keywords=['iPhone'])
        primary = [
            NewsItem(title='Apple earnings beat expectations', source='Reuters', published_at='2026-04-09', link='https://example.com/reuters-1'),
            NewsItem(title='Apple services revenue outlook', source='Reuters', published_at='2026-04-08', link='https://example.com/reuters-2'),
            NewsItem(title='Apple analyst upgrade note', source='Reuters', published_at='2026-04-07', link='https://example.com/reuters-3'),
            NewsItem(title='Apple files quarterly report', source='SEC EDGAR', published_at='2026-04-06', link='https://example.com/sec'),
            NewsItem(title='Apple announces newsroom update', source='IR RSS', published_at='2026-04-05', link='https://example.com/ir'),
        ]

        merged = _merge_news_items(item, primary, [], max_items=5, run_date=date(2026, 4, 9))

        self.assertEqual(len(merged), 4)
        self.assertEqual([entry.source for entry in merged[:2]], ['Reuters', 'Reuters'])
        self.assertIn('SEC EDGAR', {entry.source for entry in merged})
        self.assertIn('IR RSS', {entry.source for entry in merged})

    def test_merge_news_items_prioritizes_sec_earnings_filings_with_tag_weight(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology', keywords=['iPhone'])
        primary = [
            NewsItem(
                title='Apple earnings beat expectations',
                source='Reuters',
                published_at='2026-04-09',
                link='https://example.com/reuters',
            ),
            NewsItem(
                title='[실적] Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출',
                source='SEC EDGAR',
                published_at='2026-04-09',
                link='https://example.com/sec',
            ),
        ]

        merged = _merge_news_items(item, primary, [], max_items=2, run_date=date(2026, 4, 9))

        self.assertEqual(merged[0].source, 'SEC EDGAR')
        self.assertEqual(merged[1].source, 'Reuters')

    def test_merge_news_items_respects_watchlist_sec_tag_priority_override(self) -> None:
        item = WatchlistItem(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            keywords=['iPhone'],
            sec_filing_tag_priority={'실적': 0},
        )
        primary = [
            NewsItem(
                title='Apple earnings beat expectations',
                source='Reuters',
                published_at='2026-04-09',
                link='https://example.com/reuters',
            ),
            NewsItem(
                title='[실적] Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출',
                source='SEC EDGAR',
                published_at='2026-04-09',
                link='https://example.com/sec',
            ),
        ]

        merged = _merge_news_items(item, primary, [], max_items=2, run_date=date(2026, 4, 9))

        self.assertEqual(merged[0].source, 'Reuters')
        self.assertEqual(merged[1].source, 'SEC EDGAR')

    def test_merge_news_items_prefers_hard_catalyst_over_soft_recap_when_dates_match(self) -> None:
        item = WatchlistItem(ticker='AAPL', name='Apple Inc.', sector='Technology', keywords=['iPhone'])
        primary = [
            NewsItem(
                title='Why Apple stock could move next',
                source='Google News',
                published_at='2026-04-09',
                link='https://example.com/recap',
            ),
            NewsItem(
                title='[실적] Apple Inc., 8-K Item 2.02 실적 발표를 SEC에 제출',
                source='SEC EDGAR',
                published_at='2026-04-09',
                link='https://example.com/sec',
                item_number='2.02',
                catalyst_type='hard',
                importance_score=200,
            ),
        ]

        merged = _merge_news_items(item, primary, [], max_items=2, run_date=date(2026, 4, 9))

        self.assertEqual(merged[0].source, 'SEC EDGAR')

    def test_build_news_query_includes_finance_context_and_keywords(self) -> None:
        query = build_news_query(
            WatchlistItem(
                ticker='NVDA',
                name='NVIDIA Corporation',
                sector='Semiconductors',
                keywords=['GPU', 'data center', 'AI chips'],
            )
        )

        self.assertIn('NVDA', query)
        self.assertIn('NVIDIA', query)
        self.assertIn('stock', query)
        self.assertIn('GPU', query)
        self.assertIn('data center', query)
        self.assertIn('earnings guidance analyst upgrade downgrade outlook', query)

    def test_build_google_news_query_can_apply_site_filter(self) -> None:
        query = _build_google_news_query(
            WatchlistItem(
                ticker='AAPL',
                name='Apple Inc.',
                sector='Technology',
                keywords=['iPhone', 'AI'],
            ),
            'reuters.com',
        )

        self.assertIn('AAPL', query)
        self.assertIn('Apple', query)
        self.assertIn('site:reuters.com', query)

    def test_collect_rss_expands_to_expected_google_news_providers(self) -> None:
        watchlist_item = WatchlistItem(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            keywords=['iPhone', 'AI'],
        )

        with patch('src.collector.news_rss._collect_google_news_provider', return_value=[]) as collect_provider:
            from src.collector.news_rss import _collect_rss_news

            _collect_rss_news(watchlist_item, google_available=True)

        called_providers = [call.args[1]['name'] for call in collect_provider.call_args_list]
        self.assertEqual(
            called_providers,
            ['Google News', 'Yahoo Finance', 'Reuters', 'Associated Press', 'CNBC', 'MarketWatch'],
        )

    def test_collect_news_for_watchlist_merges_google_providers_and_search_results(self) -> None:
        watchlist = [
            WatchlistItem(
                ticker='AAPL',
                name='Apple Inc.',
                sector='Technology',
                keywords=['iPhone', 'AI'],
                cik='0000320193',
                ir_rss_feeds=['https://www.apple.com/newsroom/rss-feed.rss'],
            )
        ]

        with patch('src.collector.news_rss.is_env_flag_enabled', return_value=True):
            with patch('src.collector.news_rss.can_open_tcp_connection', side_effect=[True, True, True]):
                with patch(
                    'src.collector.news_rss._collect_google_news_provider',
                    side_effect=[
                        [NewsItem(title='Apple overview', source='Google News', link='https://example.com/google')],
                        [NewsItem(title='Apple on Yahoo', source='Yahoo Finance', published_at='2026-04-08', link='https://finance.yahoo.com/apple')],
                        [NewsItem(title='Apple from AP', source='Associated Press', published_at='2026-04-08', link='https://apnews.com/apple')],
                        [],
                        [],
                        [],
                    ],
                ):
                    with patch('src.collector.news_rss.collect_sec_edgar_news', return_value=[NewsItem(title='Apple filed 10-Q', source='SEC EDGAR', published_at='2026-04-08', link='https://sec.gov/apple')]):
                        with patch('src.collector.news_rss.collect_ir_rss_news', return_value=[NewsItem(title='Apple newsroom launch', source='IR RSS', published_at='2026-04-08', link='https://apple.com/newsroom')]):
                            with patch(
                                'src.collector.news_rss.search_news',
                                return_value=[NewsItem(title='Apple on Reuters', source='DuckDuckGo', link='https://www.reuters.com/apple')],
                            ):
                                news_map = collect_news_for_watchlist(watchlist, date(2026, 4, 8))

        items = news_map['AAPL']
        self.assertEqual(len(items), 5)
        self.assertEqual(items[0].source, 'SEC EDGAR')
        self.assertTrue({'Yahoo Finance', 'Associated Press', 'SEC EDGAR', 'IR RSS'}.issubset({entry.source for entry in items}))

    def test_collect_google_news_provider_drops_placeholder_titles(self) -> None:
        fake_module = types.ModuleType('feedparser')
        fake_module.parse = lambda _url: types.SimpleNamespace(entries=[
            types.SimpleNamespace(
                title='META_TITLE_QUOTE - Yahoo Finance',
                published='Mon, 14 Apr 2026 10:00:00 GMT',
                link='https://news.google.com/meta',
                source={'title': 'Yahoo Finance'},
            ),
            types.SimpleNamespace(
                title='CAT demand update',
                published='Mon, 14 Apr 2026 10:00:00 GMT',
                link='https://news.google.com/cat',
                source={'title': 'Yahoo Finance'},
            ),
        ])

        item = WatchlistItem(ticker='CAT', name='Caterpillar Inc.', sector='Industrials')
        provider = {'name': 'Yahoo Finance', 'site_filter': 'finance.yahoo.com'}

        with patch.dict(sys.modules, {'feedparser': fake_module}):
            with patch('src.collector.news_rss.record_pipeline_event') as logged:
                items = _collect_google_news_provider(item, provider)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, 'CAT demand update')
        drop_events = [call for call in logged.call_args_list if call.args[2] == 'news_title_placeholder_dropped']
        self.assertEqual(len(drop_events), 1)

    def test_search_news_maps_ddgs_results(self) -> None:
        fake_module = types.ModuleType('ddgs')
        init_kwargs: dict[str, object] = {}

        class FakeDDGS:
            def __init__(self, **kwargs: object) -> None:
                init_kwargs.update(kwargs)

            def text(self, query: str, **_: object):
                self.last_query = query
                return [
                    {
                        'title': 'Apple earnings beat expectations',
                        'href': 'https://example.com/apple-earnings',
                    }
                ]

        fake_module.DDGS = FakeDDGS

        with patch('src.collector.news_search.is_env_flag_enabled', return_value=True):
            with patch('src.collector.news_search.can_open_tcp_connection', return_value=True):
                with patch('src.collector.news_search.certifi.where', return_value='C:/certifi.pem'):
                    with patch.dict(sys.modules, {'ddgs': fake_module}):
                        items = search_news(
                            WatchlistItem(
                                ticker='AAPL',
                                name='Apple Inc.',
                                sector='Technology',
                                keywords=['iPhone', 'AI'],
                            ),
                            max_results=1,
                        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, 'Apple earnings beat expectations')
        self.assertEqual(items[0].source, 'DuckDuckGo')
        self.assertEqual(items[0].link, 'https://example.com/apple-earnings')
        self.assertEqual(init_kwargs['verify'], 'C:/certifi.pem')


if __name__ == '__main__':
    unittest.main()
