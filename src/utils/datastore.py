from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.types import TickerAnalysis

if TYPE_CHECKING:
    from src.utils.datastore_csv import CsvDatastore
    from src.utils.datastore_sqlite import SqliteDatastore

FIELDNAMES = ['date', 'ticker', 'price', 'daily_change', 'market_cap', 'trailing_pe', 'eps', '52w_high', '52w_low', 'open', 'high', 'low', 'close', 'volume']


class Datastore(ABC):
    def __init__(self, output_root: Path | None = None) -> None:
        self.output_root = output_root or Path('output')
        self.data_dir = self.output_root / 'data'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.data_dir / 'price_history.csv'

    @abstractmethod
    def append_prices(self, analyses: list[TickerAnalysis]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_period_changes(self, run_date: date) -> dict[str, dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def query_prices(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        tickers: list[str] | None = None,
    ) -> list[dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def compare_tickers(self, tickers: list[str], run_date: date) -> dict[str, dict[str, str]]:
        raise NotImplementedError

    def sync_signal_history(self, csv_path: Path) -> None:
        return None

    def append_analysis_snapshots(self, analyses: list[TickerAnalysis]) -> None:
        return None

    def record_analysis_run(self, *, run_date: date, success: bool, logger: Any | None = None) -> None:
        return None

    def get_ticker_history(self, ticker: str, *, limit: int = 90) -> list[dict[str, Any]]:
        return []

    def get_signal_stats(self) -> dict[str, Any] | None:
        return None

    def get_analysis_quality(self, *, limit: int = 30) -> list[dict[str, Any]]:
        return []


def get_datastore(output_root: Path | None = None, backend: str | None = None) -> Datastore:
    normalized_backend = (backend or os.getenv('DATASTORE_BACKEND', 'csv')).strip().lower()
    if normalized_backend == 'sqlite':
        from src.utils.datastore_sqlite import SqliteDatastore

        return SqliteDatastore(output_root=output_root)

    from src.utils.datastore_csv import CsvDatastore

    return CsvDatastore(output_root=output_root)


def build_price_history_rows(analyses: list[TickerAnalysis]) -> list[dict[str, str]]:
    rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for analysis in analyses:
        for historical_row in analysis.historical_prices:
            row_date = str(historical_row.get('date', '')).strip()
            ticker = str(historical_row.get('ticker', analysis.ticker)).strip().upper()
            if not row_date or not ticker:
                continue
            rows_by_key[(row_date, ticker)] = {
                'date': row_date,
                'ticker': ticker,
                'price': str(historical_row.get('price', 'N/A')),
                'daily_change': str(historical_row.get('daily_change', 'N/A')),
                'market_cap': str(historical_row.get('market_cap', 'N/A')),
                'trailing_pe': str(historical_row.get('trailing_pe', 'N/A')),
                'eps': str(historical_row.get('eps', 'N/A')),
                '52w_high': str(historical_row.get('52w_high', 'N/A')),
                '52w_low': str(historical_row.get('52w_low', 'N/A')),
                'open': str(historical_row.get('open', 'N/A')),
                'high': str(historical_row.get('high', 'N/A')),
                'low': str(historical_row.get('low', 'N/A')),
                'close': str(historical_row.get('close', 'N/A')),
                'volume': str(historical_row.get('volume', 'N/A')),
            }

        rows_by_key[(analysis.date, analysis.ticker)] = {
            'date': analysis.date,
            'ticker': analysis.ticker,
            'price': analysis.data_snapshot.get('Price', 'N/A'),
            'daily_change': analysis.data_snapshot.get('Daily Change', 'N/A'),
            'market_cap': analysis.data_snapshot.get('Market Cap', 'N/A'),
            'trailing_pe': analysis.data_snapshot.get('Trailing P/E', 'N/A'),
            'eps': analysis.data_snapshot.get('EPS', 'N/A'),
            '52w_high': analysis.data_snapshot.get('52W High', 'N/A'),
            '52w_low': analysis.data_snapshot.get('52W Low', 'N/A'),
            'open': analysis.data_snapshot.get('Open', 'N/A'),
            'high': analysis.data_snapshot.get('High', 'N/A'),
            'low': analysis.data_snapshot.get('Low', 'N/A'),
            'close': analysis.data_snapshot.get('Close', 'N/A'),
            'volume': analysis.data_snapshot.get('Volume', 'N/A'),
        }

    return [rows_by_key[key] for key in sorted(rows_by_key)]
