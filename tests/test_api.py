from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.types import TickerAnalysis
from src.utils.datastore import get_datastore

try:
    from src.api import main as api_main
except ModuleNotFoundError:
    api_main = None


def _analysis(run_date: str, summary: str) -> TickerAnalysis:
    return TickerAnalysis(
        ticker='AAPL',
        name='Apple Inc.',
        date=run_date,
        summary=summary,
        key_news=['뉴스'],
        news_references=[],
        financial_highlights=['실적 +5.0%'],
        risks_or_watchpoints=['260 USD 이탈 주의'],
        signal_or_takeaway='매수 관찰',
        data_snapshot={
            'Price': '100.00 USD',
            'Daily Change': '+1.00%',
            'Market Cap': '1.00T',
            'Trailing P/E': '25.00',
            'EPS': '6.00',
            '52W High': '110.00',
            '52W Low': '80.00',
        },
        news_tone={'label': 'bullish', 'confidence': 0.7},
        trade_frame={'entry_price': '100.00 USD', 'stop_loss': '95.00 USD'},
    )


@unittest.skipIf(api_main is None, 'fastapi not installed')
class ApiTests(unittest.TestCase):
    def test_ticker_detail_embeds_sqlite_history_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            data_dir = output_root / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            dashboard_path = data_dir / 'dashboard.json'
            dashboard_path.write_text(
                json.dumps(
                    {
                        'days': [
                            {
                                'date': '2026-04-08',
                                'tickers': [{'ticker': 'AAPL', 'name': 'Apple Inc.', 'summary': 'latest'}],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )
            datastore = get_datastore(output_root=output_root, backend='sqlite')
            datastore.append_analysis_snapshots([_analysis('2026-04-08', 'sqlite-summary')])

            original_root = api_main.OUTPUT_ROOT
            try:
                with patch.dict(os.environ, {'DATASTORE_BACKEND': 'sqlite'}, clear=False):
                    api_main.OUTPUT_ROOT = output_root
                    payload = api_main.ticker_detail('AAPL')
            finally:
                api_main.OUTPUT_ROOT = original_root

            self.assertIn('history', payload)
            self.assertEqual(payload['history'][0]['summary'], 'sqlite-summary')

    def test_signals_prefers_sqlite_stats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            data_dir = output_root / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            signal_csv_path = data_dir / 'signal_tracker.csv'
            signal_csv_path.write_text(
                '\n'.join(
                    [
                        'signal_date,ticker,signal_type,signal_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d',
                        '2026-04-08,AAPL,10-Q,bull,100.00,실적,bullish,추세 유지,+1.00%,+2.00%,N/A,True,True,False',
                    ]
                ),
                encoding='utf-8',
            )
            datastore = get_datastore(output_root=output_root, backend='sqlite')
            datastore.sync_signal_history(signal_csv_path)

            original_root = api_main.OUTPUT_ROOT
            try:
                with patch.dict(os.environ, {'DATASTORE_BACKEND': 'sqlite'}, clear=False):
                    api_main.OUTPUT_ROOT = output_root
                    payload = api_main.signals()
            finally:
                api_main.OUTPUT_ROOT = original_root

            self.assertEqual(payload['recent_signals'][0]['ticker'], 'AAPL')

    def test_analytics_cost_falls_back_to_log_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            output_root = workspace / 'output'
            data_dir = output_root / 'data'
            logs_dir = workspace / 'logs' / 'pipeline'
            data_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / '2026-04-08.summary.json').write_text(
                json.dumps(
                    {
                        'run_date': '2026-04-08',
                        'success': True,
                        'daily_api_cost_usd': 0.12,
                        'models_used': {'gpt-5.4-mini': 1},
                        'llm_usage': {'total_tokens': 1234},
                        'analyzer_quality': {'batch_count': 2, 'validation_failure_count': 1},
                        'ticker_fallbacks': {'AAPL': True},
                    }
                ),
                encoding='utf-8',
            )

            original_root = api_main.OUTPUT_ROOT
            try:
                with patch.dict(os.environ, {'DATASTORE_BACKEND': 'csv'}, clear=False):
                    api_main.OUTPUT_ROOT = output_root
                    payload = api_main.analytics_cost()
            finally:
                api_main.OUTPUT_ROOT = original_root

            self.assertEqual(payload['successful_runs'], 1)
            self.assertEqual(len(payload['runs']), 1)
            self.assertAlmostEqual(payload['total_cost_usd'], 0.12)


if __name__ == '__main__':
    unittest.main()
