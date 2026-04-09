from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.utils.period_changes import load_period_changes


class PeriodChangesTests(unittest.TestCase):
    def test_load_period_changes_uses_latest_available_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'price_history.csv'
            csv_path.write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low',
                        '2026-03-07,AAPL,90.00 USD,+0.10%,1T,25.0,6.0,110.0,80.0',
                        '2026-04-01,AAPL,96.00 USD,+0.10%,1T,25.0,6.0,110.0,80.0',
                        '2026-04-08,AAPL,100.00 USD,+0.10%,1T,25.0,6.0,110.0,80.0',
                    ]
                ),
                encoding='utf-8',
            )

            changes = load_period_changes(csv_path, date(2026, 4, 8))

            self.assertEqual(changes['AAPL']['7d'], '+4.17%')
            self.assertEqual(changes['AAPL']['30d'], '+11.11%')

    def test_load_period_changes_returns_na_when_anchor_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'price_history.csv'
            csv_path.write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low',
                        '2026-04-08,AAPL,100.00 USD,+0.10%,1T,25.0,6.0,110.0,80.0',
                    ]
                ),
                encoding='utf-8',
            )

            changes = load_period_changes(csv_path, date(2026, 4, 8))

            self.assertEqual(changes['AAPL']['7d'], 'N/A')
            self.assertEqual(changes['AAPL']['30d'], 'N/A')


if __name__ == '__main__':
    unittest.main()
