from __future__ import annotations

import gzip
import json
import unittest
from datetime import date
from unittest.mock import patch

from src.collector.sec_edgar import _download_submissions_payload, collect_sec_edgar_news
from src.types import WatchlistItem


class SecEdgarProviderTests(unittest.TestCase):
    def test_collect_sec_edgar_news_maps_recent_filings(self) -> None:
        item = WatchlistItem(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            cik='0000320193',
        )
        payload = {
            'name': 'Apple Inc.',
            'filings': {
                'recent': {
                    'form': ['10-Q', '8-K', '4'],
                    'filingDate': ['2026-04-08', '2026-04-07', '2026-04-06'],
                    'accessionNumber': ['0000320193-26-000010', '0000320193-26-000009', '0000320193-26-000008'],
                    'primaryDocument': ['a10-q.htm', 'a8-k.htm', 'ownership.xml'],
                }
            },
        }

        with patch('src.collector.sec_edgar.is_env_flag_enabled', return_value=True):
            with patch('src.collector.sec_edgar._download_submissions_payload', return_value=payload):
                items = collect_sec_edgar_news(item, date(2026, 4, 9), network_available=True)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].source, 'SEC EDGAR')
        self.assertEqual(items[0].title, '[실적] Apple Inc., 10-Q 분기 실적 관련 보고서를 SEC에 제출')
        self.assertEqual(
            items[0].link,
            'https://www.sec.gov/Archives/edgar/data/320193/000032019326000010/a10-q.htm',
        )

    def test_collect_sec_edgar_news_applies_dividend_tag_when_document_mentions_dividend(self) -> None:
        item = WatchlistItem(
            ticker='AAPL',
            name='Apple Inc.',
            sector='Technology',
            cik='0000320193',
        )
        payload = {
            'name': 'Apple Inc.',
            'filings': {
                'recent': {
                    'form': ['8-K'],
                    'filingDate': ['2026-04-08'],
                    'accessionNumber': ['0000320193-26-000010'],
                    'primaryDocument': ['dividend-update.htm'],
                    'primaryDocDescription': ['Dividend announcement'],
                }
            },
        }

        with patch('src.collector.sec_edgar.is_env_flag_enabled', return_value=True):
            with patch('src.collector.sec_edgar._download_submissions_payload', return_value=payload):
                items = collect_sec_edgar_news(item, date(2026, 4, 9), network_available=True)

        self.assertEqual(items[0].title, '[배당] Apple Inc., 8-K 중요 사항 공시용 보고서를 SEC에 제출')

    def test_collect_sec_edgar_news_applies_shareholder_tag_for_proxy_filings(self) -> None:
        item = WatchlistItem(
            ticker='MSFT',
            name='Microsoft Corporation',
            sector='Technology',
            cik='0000789019',
        )
        payload = {
            'name': 'Microsoft Corporation',
            'filings': {
                'recent': {
                    'form': ['DEF 14A'],
                    'filingDate': ['2026-04-08'],
                    'accessionNumber': ['0000789019-26-000010'],
                    'primaryDocument': ['proxy2026.htm'],
                    'primaryDocDescription': ['Proxy statement for annual meeting'],
                }
            },
        }

        with patch('src.collector.sec_edgar.is_env_flag_enabled', return_value=True):
            with patch('src.collector.sec_edgar._download_submissions_payload', return_value=payload):
                items = collect_sec_edgar_news(item, date(2026, 4, 9), network_available=True)

        self.assertEqual(items[0].title, '[주주총회] Microsoft Corporation, DEF 14A 주주총회 관련 위임장 설명서를 SEC에 제출')

    def test_collect_sec_edgar_news_requires_cik(self) -> None:
        item = WatchlistItem(ticker='MSFT', name='Microsoft Corporation', sector='Technology')

        with patch('src.collector.sec_edgar.is_env_flag_enabled', return_value=True):
            items = collect_sec_edgar_news(item, date(2026, 4, 9), network_available=True)

        self.assertEqual(items, [])

    def test_download_submissions_payload_handles_gzip(self) -> None:
        payload_bytes = gzip.compress(json.dumps({'name': 'Apple Inc.'}).encode('utf-8'))

        class FakeResponse:
            headers = {'Content-Encoding': 'gzip'}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return payload_bytes

        with patch('src.collector.sec_edgar.request.urlopen', return_value=FakeResponse()):
            payload = _download_submissions_payload('0000320193')

        self.assertEqual(payload['name'], 'Apple Inc.')


if __name__ == '__main__':
    unittest.main()
