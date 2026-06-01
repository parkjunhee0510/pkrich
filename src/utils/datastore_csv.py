from __future__ import annotations

import csv
import os
import tempfile
from datetime import date
from pathlib import Path

from src.types import TickerAnalysis
from src.types import CollectedTickerData
from src.utils.datastore import Datastore, FIELDNAMES, build_price_history_rows, build_price_rows_from_collected
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
        for row in _read_csv_rows(self.csv_path):
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
            rows.append(row)
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

    def upsert_collected_prices(
        self,
        collected: dict[str, CollectedTickerData],
        run_date: date,
    ) -> None:
        rows = build_price_rows_from_collected(collected, run_date)
        _write_price_rows(self.csv_path, rows)


def append_price_history_csv(path: Path, analyses: list[TickerAnalysis]) -> None:
    existing_rows = _read_csv_rows(path)
    new_rows = build_price_history_rows(analyses)
    _write_price_rows(path, new_rows, existing_rows=existing_rows)


def _write_price_rows(
    path: Path,
    new_rows: list[dict[str, str]],
    *,
    existing_rows: list[dict[str, str]] | None = None,
) -> None:
    existing = existing_rows if existing_rows is not None else _read_csv_rows(path)
    replacement_keys = {(row.get('date'), row.get('ticker')) for row in new_rows}
    updated_rows = [row for row in existing if (row.get('date'), row.get('ticker')) not in replacement_keys]
    updated_rows.extend(new_rows)
    updated_rows.sort(key=lambda row: (row['date'], row['ticker']))

    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace: never truncate the existing price history on a crash.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix='price_history.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(updated_rows)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _parse_date(raw_value: str) -> date | None:
    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        return None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8-sig', newline='') as csv_file:
        reader = csv.DictReader(csv_file)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized_row: dict[str, str] = {}
            for key, value in row.items():
                if not key:
                    continue
                normalized_row[key.lstrip('\ufeff')] = str(value)
            if normalized_row:
                rows.append(normalized_row)
        return rows
