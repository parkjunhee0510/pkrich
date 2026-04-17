from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import NewsItem, TickerAnalysis
from src.utils.datastore import get_datastore


def _analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker='AAPL',
        name='Apple Inc.',
        date='2026-04-08',
        summary='Summary',
        key_news=['earnings beat'],
        news_references=[
            NewsItem(
                title='[실적] Apple, 10-Q',
                source='SEC EDGAR',
                published_at='2026-04-08',
                link='https://example.com/sec',
                form_type='10-Q',
                catalyst_type='hard',
                importance_score=200,
            )
        ],
        financial_highlights=['시가총액: 1.00T'],
        risks_or_watchpoints=['체크'],
        signal_or_takeaway='상승 지속 점검',
        data_snapshot={'Price': '100.00 USD'},
        trade_frame={'base_scenario': '박스권'},
        news_tone={'label': 'bullish'},
    )


class CsvDatastoreSignalApiTests(unittest.TestCase):
    def test_record_and_load_via_csv_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='csv')
            datastore.record_signals([_analysis()], date(2026, 4, 8), {'AAPL': 100.0})

            stats = datastore.load_signal_stats_data()
            rows = datastore.load_signal_rows_data()
            recent = datastore.load_recent_signals_data('AAPL', limit=3)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['ticker'], 'AAPL')
            self.assertEqual(stats['summary_by_direction']['bull']['count'], 1)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]['direction'], 'bull')


class SqliteDatastoreSignalApiTests(unittest.TestCase):
    def test_record_signals_dual_writes_csv_and_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='sqlite')
            datastore.record_signals([_analysis()], date(2026, 4, 8), {'AAPL': 100.0})

            self.assertTrue(datastore.signal_csv_path.exists())
            connection = sqlite3.connect(datastore.sqlite_path)
            try:
                count = connection.execute(
                    'SELECT COUNT(*) FROM signal_history'
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(count, 1)

            stats = datastore.get_signal_stats()
            self.assertIsNotNone(stats)
            self.assertEqual(stats['summary_by_direction']['bull']['count'], 1)


if __name__ == '__main__':
    unittest.main()
