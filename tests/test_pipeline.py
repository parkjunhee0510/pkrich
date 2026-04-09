from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_writes_expected_outputs_in_fallback_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_dir = temp_path / 'config'
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / 'watchlist.yaml').write_text(
                '\n'.join(
                    [
                        'watchlist:',
                        '  - ticker: AAPL',
                        '    name: Apple Inc.',
                        '    sector: Technology',
                        '    keywords: ["iPhone", "AI"]',
                    ]
                ),
                encoding='utf-8',
            )

            with patch.dict(os.environ, {'ENABLE_EXTERNAL_FETCH': 'false'}, clear=False):
                current_dir = os.getcwd()
                try:
                    os.chdir(temp_path)
                    run_pipeline(run_date=date(2026, 4, 8))
                finally:
                    os.chdir(current_dir)

            daily_path = temp_path / 'output' / 'daily' / '2026-04-08.md'
            ticker_path = temp_path / 'output' / 'tickers' / 'AAPL' / '2026-04-08.md'
            csv_path = temp_path / 'output' / 'data' / 'price_history.csv'
            signal_csv_path = temp_path / 'output' / 'data' / 'signal_tracker.csv'
            dashboard_path = temp_path / 'output' / 'data' / 'dashboard.json'
            timeline_path = temp_path / 'output' / 'data' / 'ticker_timelines.json'
            log_summary_path = temp_path / 'logs' / 'pipeline' / '2026-04-08.summary.json'

            self.assertTrue(daily_path.exists())
            self.assertTrue(ticker_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertTrue(signal_csv_path.exists())
            self.assertTrue(dashboard_path.exists())
            self.assertTrue(timeline_path.exists())
            self.assertTrue(log_summary_path.exists())
            self.assertIn('AAPL', daily_path.read_text(encoding='utf-8'))
            self.assertIn('외부 수집이 비활성화되어 뉴스 요청을 건너뛰었습니다.', ticker_path.read_text(encoding='utf-8'))

    def test_run_pipeline_writes_weekly_report_and_obsidian_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_dir = temp_path / 'config'
            vault_dir = temp_path / 'vault'
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / 'watchlist.yaml').write_text(
                '\n'.join(
                    [
                        'watchlist:',
                        '  - ticker: AAPL',
                        '    name: Apple Inc.',
                        '    sector: Technology',
                        '    keywords: ["iPhone", "AI"]',
                    ]
                ),
                encoding='utf-8',
            )

            with patch.dict(
                os.environ,
                {
                    'ENABLE_EXTERNAL_FETCH': 'false',
                    'OBSIDIAN_VAULT_PATH': str(vault_dir),
                },
                clear=False,
            ):
                current_dir = os.getcwd()
                try:
                    os.chdir(temp_path)
                    run_pipeline(run_date=date(2026, 4, 8))
                finally:
                    os.chdir(current_dir)

            iso_year, iso_week, _ = date(2026, 4, 8).isocalendar()
            weekly_path = temp_path / 'output' / 'daily' / 'weekly' / f'{iso_year}-W{iso_week:02d}.md'
            mirrored_daily = vault_dir / 'pkrich' / 'daily' / '2026-04-08.md'
            mirrored_ticker = vault_dir / 'pkrich' / 'tickers' / 'AAPL' / '2026-04-08.md'

            self.assertTrue(weekly_path.exists())
            self.assertTrue(mirrored_daily.exists())
            self.assertTrue(mirrored_ticker.exists())
            self.assertIn('## 주간 시장 개요', weekly_path.read_text(encoding='utf-8'))
            self.assertEqual(
                (temp_path / 'output' / 'daily' / '2026-04-08.md').read_text(encoding='utf-8'),
                mirrored_daily.read_text(encoding='utf-8'),
            )


if __name__ == '__main__':
    unittest.main()
