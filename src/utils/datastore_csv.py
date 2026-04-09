from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from src.types import TickerAnalysis
from src.utils.datastore import Datastore, FIELDNAMES, build_price_history_rows
from src.utils.period_changes import load_period_changes_from_rows


class CsvDatastore(Datastore):
    def append_prices(self, analyses: list[TickerAnalysis]) -> None:
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
        if not self.csv_path.exists():
            return []
        ticker_filter = {ticker.upper() for ticker in tickers or []}
        rows: list[dict[str, str]] = []
        with self.csv_path.open('r', encoding='utf-8', newline='') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                row_date = _parse_date(row.get('date', ''))
                ticker = str(row.get('ticker', '')).strip().upper()
                if row_date is None or not ticker:
                    continue
                if start_date and row_date < start_date:
                    continue
                if end_date and row_date > end_date:
                    continue
                if ticker_filter and ticker not in ticker_filter:
                    continue
                rows.append({key: str(value) for key, value in row.items() if key})
        return sorted(rows, key=lambda row: (row.get('date', ''), row.get('ticker', '')))

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


def append_price_history_csv(path: Path, analyses: list[TickerAnalysis]) -> None:
    existing_rows: list[dict[str, str]] = []
    if path.exists():
        with path.open('r', encoding='utf-8', newline='') as csv_file:
            existing_rows = list(csv.DictReader(csv_file))

    replacement_keys = {(analysis.date, analysis.ticker) for analysis in analyses}
    updated_rows = [row for row in existing_rows if (row.get('date'), row.get('ticker')) not in replacement_keys]
    updated_rows.extend(build_price_history_rows(analyses))
    updated_rows.sort(key=lambda row: (row['date'], row['ticker']))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(updated_rows)


def _parse_date(raw_value: str) -> date | None:
    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        return None
