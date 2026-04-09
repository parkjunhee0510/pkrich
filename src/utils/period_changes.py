from __future__ import annotations

import csv
import re
from datetime import date, timedelta
from pathlib import Path


_NUMBER_PATTERN = re.compile(r'[-+]?\d[\d,]*\.?\d*')
_PERIODS = (7, 30)


def load_period_changes(csv_path: Path, run_date: date) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        return {}

    with csv_path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader]
    return load_period_changes_from_rows(rows, run_date)


def load_period_changes_from_rows(rows: list[dict[str, str]], run_date: date) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[tuple[date, float]]] = {}
    for row in rows:
        ticker = str(row.get('ticker', '')).strip().upper()
        row_date = _parse_date(row.get('date', ''))
        price = _parse_numeric(str(row.get('price', '')))
        if not ticker or row_date is None or price is None:
            continue
        grouped.setdefault(ticker, []).append((row_date, price))

    result: dict[str, dict[str, str]] = {}
    for ticker, ticker_rows in grouped.items():
        sorted_rows = sorted(ticker_rows, key=lambda item: item[0])
        current_row = _latest_row_on_or_before(sorted_rows, run_date)
        if current_row is None:
            result[ticker] = {'7d': 'N/A', '30d': 'N/A'}
            continue

        current_date, current_price = current_row
        result[ticker] = {}
        for period in _PERIODS:
            anchor_row = _latest_row_on_or_before(sorted_rows, current_date - timedelta(days=period))
            key = f'{period}d'
            if anchor_row is None or anchor_row[1] == 0:
                result[ticker][key] = 'N/A'
                continue
            result[ticker][key] = _format_percent(((current_price - anchor_row[1]) / anchor_row[1]) * 100)
    return result


def _latest_row_on_or_before(rows: list[tuple[date, float]], target: date) -> tuple[date, float] | None:
    latest: tuple[date, float] | None = None
    for row in rows:
        if row[0] <= target:
            latest = row
        else:
            break
    return latest


def _parse_date(raw_value: str) -> date | None:
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        return None


def _parse_numeric(raw_value: str) -> float | None:
    match = _NUMBER_PATTERN.search(raw_value)
    if not match:
        return None
    try:
        return float(match.group(0).replace(',', ''))
    except ValueError:
        return None


def _format_percent(value: float) -> str:
    return f'{value:+.2f}%'
