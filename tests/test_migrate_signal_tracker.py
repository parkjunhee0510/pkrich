from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import NewsItem, TickerAnalysis
from src.utils.migrate_signal_tracker import migrate_signal_tracker
from src.utils.signal_tracker import record_signals


def _analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker='AAPL',
        name='Apple Inc.',
        date='2026-04-08',
        summary='Summary',
        key_news=['earnings beat'],
        news_references=[
            NewsItem(
                title='[실적] Apple Inc., 10-Q',
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


class MigrateSignalTrackerTests(unittest.TestCase):
    def test_migrate_row_count_matches_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'signal_tracker.csv'
            sqlite_path = Path(temp_dir) / 'price_history.sqlite'
            record_signals([_analysis()], date(2026, 4, 8), {'AAPL': 100.0}, csv_path)

            result = migrate_signal_tracker(csv_path=csv_path, sqlite_path=sqlite_path)

            self.assertEqual(result['csv_rows'], result['sqlite_rows'])
            self.assertEqual(result['csv_rows'], 1)

            connection = sqlite3.connect(sqlite_path)
            try:
                row = connection.execute(
                    'SELECT ticker, signal_direction, catalyst_tag FROM signal_history'
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row, ('AAPL', 'bull', '실적'))

    def test_migrate_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'signal_tracker.csv'
            sqlite_path = Path(temp_dir) / 'price_history.sqlite'
            record_signals([_analysis()], date(2026, 4, 8), {'AAPL': 100.0}, csv_path)

            migrate_signal_tracker(csv_path=csv_path, sqlite_path=sqlite_path)
            result = migrate_signal_tracker(csv_path=csv_path, sqlite_path=sqlite_path)

            self.assertEqual(result['csv_rows'], 1)
            self.assertEqual(result['sqlite_rows'], 1)

    def test_migrate_missing_csv_yields_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'missing.csv'
            sqlite_path = Path(temp_dir) / 'price_history.sqlite'

            result = migrate_signal_tracker(csv_path=csv_path, sqlite_path=sqlite_path)

            self.assertEqual(result, {'csv_rows': 0, 'sqlite_rows': 0})


if __name__ == '__main__':
    unittest.main()
