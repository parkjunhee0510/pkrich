from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import MarketRegime, NewsItem, TickerAnalysis, TickerDecision
from src.utils.datastore import get_datastore
from src.utils.signal_tracker import (
    _classify_rule_direction,
    _classify_signal_direction,
)


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

    def test_load_signal_rows_preserves_decision_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='sqlite')
            datastore.record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {'AAPL': 100.0},
                decisions=[
                    TickerDecision(
                        ticker='AAPL',
                        action='buy',
                        conviction=72,
                        raw_conviction=80,
                        factors={'momentum': 1.5},
                        factor_reasoning={'momentum': 'trend improved'},
                        confidence_meta={'data_quality_score': 0.88},
                    )
                ],
                market_regime=MarketRegime(regime='risk_on', sub_regime='growth'),
            )

            rows = datastore.load_signal_rows_data()

        self.assertEqual(rows[0]['action'], 'buy')
        self.assertEqual(rows[0]['conviction'], '72')
        self.assertEqual(rows[0]['raw_conviction'], '80')
        self.assertEqual(rows[0]['regime'], 'risk_on')
        self.assertEqual(rows[0]['sub_regime'], 'growth')
        self.assertEqual(json.loads(rows[0]['factors_json']), {'momentum': 1.5})
        self.assertEqual(json.loads(rows[0]['factor_reasoning_json']), {'momentum': 'trend improved'})
        self.assertEqual(json.loads(rows[0]['confidence_meta_json']), {'data_quality_score': 0.88})


class RuleDirectionClassifierTests(unittest.TestCase):
    """`_classify_rule_direction` must be independent of LLM-generated text."""

    def test_buy_action_maps_to_bull(self) -> None:
        decision = TickerDecision(ticker='AAPL', action='buy', conviction=72)
        self.assertEqual(_classify_rule_direction(decision), 'bull')

    def test_avoid_action_maps_to_bear(self) -> None:
        decision = TickerDecision(ticker='AAPL', action='avoid', conviction=30)
        self.assertEqual(_classify_rule_direction(decision), 'bear')

    def test_watch_action_maps_to_neutral(self) -> None:
        decision = TickerDecision(ticker='AAPL', action='watch', conviction=50)
        self.assertEqual(_classify_rule_direction(decision), 'neutral')

    def test_missing_decision_falls_back(self) -> None:
        self.assertEqual(_classify_rule_direction(None, fallback='bull'), 'bull')
        self.assertEqual(_classify_rule_direction(None), 'neutral')

    def test_rule_direction_can_diverge_from_llm_text_direction(self) -> None:
        analysis = _analysis()  # LLM text leans bullish via news_tone='bullish'
        llm_dir = _classify_signal_direction(analysis)
        rule_dir = _classify_rule_direction(
            TickerDecision(ticker='AAPL', action='avoid', conviction=30)
        )
        self.assertEqual(llm_dir, 'bull')
        self.assertEqual(rule_dir, 'bear')
        self.assertNotEqual(rule_dir, llm_dir)


class SignalTrackerDirectionDecouplingTests(unittest.TestCase):
    """Persisted rows must carry distinct rule vs LLM directions when they disagree."""

    def test_recorded_row_has_independent_directions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='csv')
            datastore.record_signals(
                [_analysis()],
                date(2026, 4, 8),
                {'AAPL': 100.0},
                decisions=[
                    TickerDecision(ticker='AAPL', action='avoid', conviction=28),
                ],
                market_regime=MarketRegime(regime='neutral'),
            )
            rows = datastore.load_signal_rows_data()

        self.assertEqual(rows[0]['signal_direction'], 'bear')  # rule (avoid)
        self.assertEqual(rows[0]['llm_direction'], 'bull')      # LLM text (bullish tone)
        self.assertNotEqual(rows[0]['signal_direction'], rows[0]['llm_direction'])


if __name__ == '__main__':
    unittest.main()
