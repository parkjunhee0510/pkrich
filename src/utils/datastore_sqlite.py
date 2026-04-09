from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from src.types import TickerAnalysis
from src.utils.datastore import Datastore, FIELDNAMES, build_price_history_rows
from src.utils.datastore_csv import append_price_history_csv
from src.utils.period_changes import load_period_changes_from_rows


class SqliteDatastore(Datastore):
    def __init__(self, output_root: Path | None = None) -> None:
        super().__init__(output_root=output_root)
        self.sqlite_path = self.data_dir / 'price_history.sqlite'
        self._ensure_schema()

    def append_prices(self, analyses: list[TickerAnalysis]) -> None:
        rows = build_price_history_rows(analyses)
        self._upsert_rows(rows)
        append_price_history_csv(self.csv_path, analyses)

    def load_period_changes(self, run_date: date) -> dict[str, dict[str, str]]:
        return load_period_changes_from_rows(self.query_prices(), run_date)

    def query_prices(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        tickers: list[str] | None = None,
    ) -> list[dict[str, str]]:
        clauses: list[str] = []
        values: list[str] = []
        if start_date is not None:
            clauses.append('date >= ?')
            values.append(start_date.isoformat())
        if end_date is not None:
            clauses.append('date <= ?')
            values.append(end_date.isoformat())
        if tickers:
            placeholders = ','.join('?' for _ in tickers)
            clauses.append(f'ticker IN ({placeholders})')
            values.extend(ticker.upper() for ticker in tickers)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        query = f"SELECT date, ticker, price, daily_change, market_cap, trailing_pe, eps, high_52w, low_52w FROM prices {where_clause} ORDER BY date, ticker"
        connection = sqlite3.connect(self.sqlite_path)
        try:
            cursor = connection.execute(query, values)
            return [
                {
                    'date': row[0],
                    'ticker': row[1],
                    'price': row[2],
                    'daily_change': row[3],
                    'market_cap': row[4],
                    'trailing_pe': row[5],
                    'eps': row[6],
                    '52w_high': row[7],
                    '52w_low': row[8],
                }
                for row in cursor.fetchall()
            ]
        finally:
            connection.close()

    def compare_tickers(self, tickers: list[str], run_date: date) -> dict[str, dict[str, str]]:
        rows = self.query_prices(tickers=tickers)
        period_changes = load_period_changes_from_rows(rows, run_date)
        latest_by_ticker: dict[str, dict[str, str]] = {}
        for row in rows:
            latest_by_ticker[row['ticker']] = row
        result: dict[str, dict[str, str]] = {}
        for ticker in tickers:
            normalized = ticker.upper()
            latest_row = latest_by_ticker.get(normalized, {})
            result[normalized] = {
                'price': latest_row.get('price', 'N/A'),
                'daily_change': latest_row.get('daily_change', 'N/A'),
                '7d': period_changes.get(normalized, {}).get('7d', 'N/A'),
                '30d': period_changes.get(normalized, {}).get('30d', 'N/A'),
            }
        return result

    def _ensure_schema(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS prices (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    price TEXT NOT NULL,
                    daily_change TEXT NOT NULL,
                    market_cap TEXT NOT NULL,
                    trailing_pe TEXT NOT NULL,
                    eps TEXT NOT NULL,
                    high_52w TEXT NOT NULL,
                    low_52w TEXT NOT NULL,
                    PRIMARY KEY (date, ticker)
                )
                '''
            )
            connection.commit()
        finally:
            connection.close()

    def _upsert_rows(self, rows: list[dict[str, str]]) -> None:
        if not rows:
            return
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.executemany(
                '''
                INSERT OR REPLACE INTO prices (
                    date, ticker, price, daily_change, market_cap, trailing_pe, eps, high_52w, low_52w
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    (
                        row['date'],
                        row['ticker'],
                        row['price'],
                        row['daily_change'],
                        row['market_cap'],
                        row['trailing_pe'],
                        row['eps'],
                        row['52w_high'],
                        row['52w_low'],
                    )
                    for row in rows
                ],
            )
            connection.commit()
        finally:
            connection.close()
