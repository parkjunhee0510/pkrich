from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import MarketRegime, NewsItem, TickerAnalysis, TickerDecision
from src.utils.datastore import get_datastore
from src.utils.signal_tracker import FIELDNAMES


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
            self.assertEqual(rows[0]['llm_direction'], 'bull')
            self.assertEqual(stats['summary_by_direction']['bull']['count'], 1)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]['direction'], 'bull')
            self.assertEqual(recent[0]['llm_direction'], 'bull')


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

            rows = datastore.load_signal_rows_data()
            self.assertEqual(rows[0]['barrier_label'], 'pending')
            self.assertEqual(rows[0]['barrier_hit_day'], '')
            self.assertEqual(rows[0]['barrier_return'], '')
            self.assertEqual(rows[0]['barrier_date'], '')

    def test_sync_signal_history_preserves_triple_barrier_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='sqlite')
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
            datastore.signal_csv_path.parent.mkdir(parents=True, exist_ok=True)
            with datastore.signal_csv_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow(row)

            datastore.sync_signal_history(datastore.signal_csv_path)

            rows = datastore.load_signal_rows_data()
            stats = datastore.get_signal_stats()

        self.assertEqual(rows[0]['ticker'], 'AAPL')
        self.assertEqual(rows[0]['barrier_label'], 'take_profit')
        self.assertEqual(rows[0]['barrier_hit_day'], '5')
        self.assertEqual(rows[0]['barrier_return'], '+2.00%')
        self.assertEqual(rows[0]['barrier_date'], '2026-05-05')
        self.assertIsNotNone(stats)
        self.assertEqual(stats['recent_signals'][0]['barrier_label'], 'take_profit')

    def test_record_signals_persists_decision_metadata_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='sqlite')
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

            datastore.record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {'AAPL': 100.0},
                decisions=[decision],
                market_regime=regime,
            )

            rows = datastore.load_signal_rows_data()

        self.assertEqual(rows[0]['action'], 'buy')
        self.assertEqual(rows[0]['conviction'], '72')
        self.assertEqual(rows[0]['raw_conviction'], '80')
        self.assertEqual(rows[0]['regime'], 'risk_on')
        self.assertEqual(rows[0]['sub_regime'], 'growth')
        self.assertEqual(json.loads(rows[0]['factors_json']), {'momentum': 1.5})
        self.assertEqual(json.loads(rows[0]['factor_reasoning_json']), {'momentum': 'trend'})
        self.assertEqual(json.loads(rows[0]['confidence_meta_json']), {'data_quality_score': 0.88})


if __name__ == '__main__':
    unittest.main()
