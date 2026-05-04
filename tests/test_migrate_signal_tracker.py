from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import MarketRegime, NewsItem, TickerAnalysis, TickerDecision
from src.utils.migrate_signal_tracker import migrate_signal_tracker
from src.utils.signal_tracker import FIELDNAMES, record_signals


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

    def test_migrate_preserves_triple_barrier_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'signal_tracker.csv'
            sqlite_path = Path(temp_dir) / 'price_history.sqlite'
            row = {
                'signal_date': '2026-05-01',
                'ticker': 'aapl',
                'signal_type': '10-Q',
                'signal_direction': 'bull',
                'llm_direction': 'bull',
                'signal_price': '100.00',
                'catalyst_tag': 'earnings',
                'news_tone': 'bullish',
                'trade_frame_scenario': 'base',
                'conviction': '72',
                'raw_conviction': '80',
                'action': 'buy',
                'regime': 'risk_on',
                'sub_regime': 'growth',
                'factors_json': '{}',
                'factor_reasoning_json': '{}',
                'confidence_meta_json': '{}',
                'return_1d': 'N/A',
                'return_5d': 'N/A',
                'return_20d': 'N/A',
                'evaluated_1d': 'False',
                'evaluated_5d': 'False',
                'evaluated_20d': 'False',
                'barrier_label': 'take_profit',
                'barrier_hit_day': '5',
                'barrier_return': '+2.00%',
                'barrier_date': '2026-05-05',
            }
            with csv_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow(row)

            migrate_signal_tracker(csv_path=csv_path, sqlite_path=sqlite_path)

            connection = sqlite3.connect(sqlite_path)
            try:
                migrated = connection.execute(
                    '''
                    SELECT ticker, barrier_label, barrier_hit_day, barrier_return, barrier_date
                    FROM signal_history
                    '''
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(migrated, ('AAPL', 'take_profit', '5', '+2.00%', '2026-05-05'))

    def test_migrate_preserves_decision_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'signal_tracker.csv'
            sqlite_path = Path(temp_dir) / 'price_history.sqlite'
            decision = TickerDecision(
                ticker='AAPL',
                action='buy',
                conviction=72,
                raw_conviction=80,
                factors={'momentum': 1.5},
                factor_reasoning={'momentum': 'trend'},
                confidence_meta={'data_quality_score': 0.88},
            )
            regime = MarketRegime(regime='risk_on', sub_regime='growth', confidence=70)
            record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {'AAPL': 100.0},
                csv_path,
                decisions=[decision],
                market_regime=regime,
            )

            migrate_signal_tracker(csv_path=csv_path, sqlite_path=sqlite_path)

            connection = sqlite3.connect(sqlite_path)
            try:
                row = connection.execute(
                    '''
                    SELECT
                        ticker,
                        action,
                        conviction,
                        regime,
                        factors_json,
                        factor_reasoning_json,
                        confidence_meta_json
                    FROM signal_history
                    '''
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(row[0], 'AAPL')
        self.assertEqual(row[1], 'buy')
        self.assertEqual(row[2], '72')
        self.assertEqual(row[3], 'risk_on')
        self.assertEqual(json.loads(row[4]), {'momentum': 1.5})
        self.assertEqual(json.loads(row[5]), {'momentum': 'trend'})
        self.assertEqual(json.loads(row[6]), {'data_quality_score': 0.88})


if __name__ == '__main__':
    unittest.main()
