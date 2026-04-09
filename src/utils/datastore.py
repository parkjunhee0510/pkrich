from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from src.types import TickerAnalysis

if TYPE_CHECKING:
    from src.utils.datastore_csv import CsvDatastore
    from src.utils.datastore_sqlite import SqliteDatastore

FIELDNAMES = ['date', 'ticker', 'price', 'daily_change', 'market_cap', 'trailing_pe', 'eps', '52w_high', '52w_low']


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


def get_datastore(output_root: Path | None = None, backend: str | None = None) -> Datastore:
    normalized_backend = (backend or os.getenv('DATASTORE_BACKEND', 'csv')).strip().lower()
    if normalized_backend == 'sqlite':
        from src.utils.datastore_sqlite import SqliteDatastore

        return SqliteDatastore(output_root=output_root)

    from src.utils.datastore_csv import CsvDatastore

    return CsvDatastore(output_root=output_root)


def build_price_history_rows(analyses: list[TickerAnalysis]) -> list[dict[str, str]]:
    return [
        {
            'date': analysis.date,
            'ticker': analysis.ticker,
            'price': analysis.data_snapshot.get('Price', 'N/A'),
            'daily_change': analysis.data_snapshot.get('Daily Change', 'N/A'),
            'market_cap': analysis.data_snapshot.get('Market Cap', 'N/A'),
            'trailing_pe': analysis.data_snapshot.get('Trailing P/E', 'N/A'),
            'eps': analysis.data_snapshot.get('EPS', 'N/A'),
            '52w_high': analysis.data_snapshot.get('52W High', 'N/A'),
            '52w_low': analysis.data_snapshot.get('52W Low', 'N/A'),
        }
        for analysis in analyses
    ]
