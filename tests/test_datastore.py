from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.types import TickerAnalysis
from src.utils.datastore import get_datastore
from src.utils.migrate_csv_to_sqlite import migrate_csv_to_sqlite


def _analysis(run_date: str, price: str) -> TickerAnalysis:
    return TickerAnalysis(
        ticker='AAPL',
        name='Apple Inc.',
        date=run_date,
        summary='요약',
        key_news=['뉴스'],
        news_references=[],
        financial_highlights=['시가총액: 1.00T'],
        risks_or_watchpoints=['체크'],
        signal_or_takeaway='추적 유지',
        data_snapshot={
            'Price': price,
            'Daily Change': '+1.00%',
            'Market Cap': '1.00T',
            'Trailing P/E': '25.00',
            'EPS': '6.00',
            '52W High': '110.00',
            '52W Low': '80.00',
        },
    )


class DatastoreTests(unittest.TestCase):
    def test_csv_datastore_appends_and_compares_prices(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='csv')
            datastore.append_prices([_analysis('2026-04-01', '96.00 USD')])
            datastore.append_prices([_analysis('2026-04-08', '100.00 USD')])

            comparison = datastore.compare_tickers(['AAPL'], date(2026, 4, 8))

        self.assertEqual(comparison['AAPL']['price'], '100.00 USD')
        self.assertEqual(comparison['AAPL']['7d'], '+4.17%')

    def test_sqlite_datastore_mirrors_csv_and_queries_period_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'output'
            datastore = get_datastore(output_root=output_root, backend='sqlite')
            datastore.append_prices([_analysis('2026-03-09', '90.00 USD')])
            datastore.append_prices([_analysis('2026-04-08', '100.00 USD')])

            rows = datastore.query_prices()
            period_changes = datastore.load_period_changes(date(2026, 4, 8))

            self.assertTrue((output_root / 'data' / 'price_history.csv').exists())
            self.assertTrue((output_root / 'data' / 'price_history.sqlite').exists())
            self.assertEqual(len(rows), 2)
            self.assertEqual(period_changes['AAPL']['30d'], '+11.11%')

    def test_migrate_csv_to_sqlite_preserves_row_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / 'price_history.csv'
            sqlite_path = Path(temp_dir) / 'price_history.sqlite'
            csv_path.write_text(
                '\n'.join(
                    [
                        'date,ticker,price,daily_change,market_cap,trailing_pe,eps,52w_high,52w_low',
                        '2026-04-01,AAPL,96.00 USD,+1.00%,1.00T,25.00,6.00,110.00,80.00',
                        '2026-04-08,AAPL,100.00 USD,+1.00%,1.00T,25.00,6.00,110.00,80.00',
                    ]
                ),
                encoding='utf-8',
            )

            result = migrate_csv_to_sqlite(csv_path=csv_path, sqlite_path=sqlite_path)

        self.assertEqual(result['csv_rows'], 2)
        self.assertEqual(result['sqlite_rows'], 2)


if __name__ == '__main__':
    unittest.main()
