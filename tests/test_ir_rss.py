from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from src.collector.ir_rss import collect_ir_rss_news
from src.types import WatchlistItem


class IrrssProviderTests(unittest.TestCase):
    def test_collect_ir_rss_news_maps_feed_entries(self) -> None:
        fake_module = types.ModuleType('feedparser')

        def fake_parse(_url: str):
            return types.SimpleNamespace(
                feed=types.SimpleNamespace(title='Apple Newsroom'),
                entries=[
                    types.SimpleNamespace(
                        title='Apple announces developer event',
                        published='Wed, 08 Apr 2026 10:00:00 GMT',
                        link='https://www.apple.com/newsroom/article',
                    )
                ]
            )

        fake_module.parse = fake_parse
        item = WatchlistItem(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            ir_rss_feeds=['https://www.apple.com/newsroom/rss-feed.rss'],
        )

        with patch('src.collector.ir_rss.is_env_flag_enabled', return_value=True):
            with patch.dict(sys.modules, {'feedparser': fake_module}):
                items = collect_ir_rss_news(item)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, 'Apple Newsroom')
        self.assertEqual(items[0].title, 'Apple announces developer event')

    def test_collect_ir_rss_news_infers_brand_name_from_feed_url(self) -> None:
        fake_module = types.ModuleType('feedparser')

        def fake_parse(_url: str):
            return types.SimpleNamespace(
                feed=types.SimpleNamespace(title=''),
                entries=[
                    types.SimpleNamespace(
                        title='Microsoft announces Copilot update',
                        published='Wed, 08 Apr 2026 10:00:00 GMT',
                        link='https://news.microsoft.com/source/story',
                    )
                ]
            )

        fake_module.parse = fake_parse
        item = WatchlistItem(
            ticker='MSFT',
            name='Microsoft Corporation',
            sector='Technology',
            ir_rss_feeds=['https://news.microsoft.com/source/feed/'],
        )

        with patch('src.collector.ir_rss.is_env_flag_enabled', return_value=True):
            with patch.dict(sys.modules, {'feedparser': fake_module}):
                items = collect_ir_rss_news(item)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, 'Microsoft Source')

    def test_collect_ir_rss_news_uses_configured_brand_name_mapping(self) -> None:
        fake_module = types.ModuleType('feedparser')

        def fake_parse(_url: str):
            return types.SimpleNamespace(
                feed=types.SimpleNamespace(title=''),
                entries=[
                    types.SimpleNamespace(
                        title='NVIDIA announces GPU platform',
                        published='Wed, 08 Apr 2026 10:00:00 GMT',
                        link='https://nvidianews.nvidia.com/story',
                    )
                ]
            )

        fake_module.parse = fake_parse
        item = WatchlistItem(
            ticker='NVDA',
            name='NVIDIA Corporation',
            sector='Semiconductors',
            ir_rss_feeds=['https://nvidianews.nvidia.com/cats/press_release.xml'],
        )

        with patch('src.collector.ir_rss.is_env_flag_enabled', return_value=True):
            with patch('src.collector.ir_rss.load_simple_mapping', return_value={'ir_source_names': {'nvidianews.nvidia.com': 'NVIDIA Investor News'}}):
                with patch.dict(sys.modules, {'feedparser': fake_module}):
                    items = collect_ir_rss_news(item)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, 'NVIDIA Investor News')

    def test_collect_ir_rss_news_prefers_watchlist_override_over_global_mapping(self) -> None:
        fake_module = types.ModuleType('feedparser')

        def fake_parse(_url: str):
            return types.SimpleNamespace(
                feed=types.SimpleNamespace(title=''),
                entries=[
                    types.SimpleNamespace(
                        title='Custom Microsoft update',
                        published='Wed, 08 Apr 2026 10:00:00 GMT',
                        link='https://news.microsoft.com/source/story',
                    )
                ]
            )

        fake_module.parse = fake_parse
        item = WatchlistItem(
            ticker='MSFT',
            name='Microsoft Corporation',
            sector='Technology',
            ir_rss_feeds=['https://news.microsoft.com/source/feed/'],
            ir_source_names={'news.microsoft.com': 'MSFT Investor Wire'},
        )

        with patch('src.collector.ir_rss.is_env_flag_enabled', return_value=True):
            with patch('src.collector.ir_rss.load_simple_mapping', return_value={'ir_source_names': {'news.microsoft.com': 'Microsoft Source'}}):
                with patch.dict(sys.modules, {'feedparser': fake_module}):
                    items = collect_ir_rss_news(item)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, 'MSFT Investor Wire')

    def test_collect_ir_rss_news_returns_empty_without_feeds(self) -> None:
        item = WatchlistItem(ticker='NVDA', name='NVIDIA Corporation', sector='Semiconductors')

        with patch('src.collector.ir_rss.is_env_flag_enabled', return_value=True):
            items = collect_ir_rss_news(item)

        self.assertEqual(items, [])


if __name__ == '__main__':
    unittest.main()
