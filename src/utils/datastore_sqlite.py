from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from src.types import CollectedTickerData, TickerAnalysis
from src.utils.datastore import Datastore, build_price_history_rows, build_price_rows_from_collected
from src.utils.datastore_csv import append_price_history_csv
from src.utils.period_changes import load_period_changes_from_rows
from src.utils.signal_tracker import build_signal_stats_from_rows, load_signal_rows

PRICE_COLUMN_DEFAULTS: dict[str, str] = {
    'open': "TEXT NOT NULL DEFAULT 'N/A'",
    'high': "TEXT NOT NULL DEFAULT 'N/A'",
    'low': "TEXT NOT NULL DEFAULT 'N/A'",
    'close': "TEXT NOT NULL DEFAULT 'N/A'",
    'volume': "TEXT NOT NULL DEFAULT 'N/A'",
}


class SqliteDatastore(Datastore):
    def __init__(self, output_root: Path | None = None) -> None:
        super().__init__(output_root=output_root)
        self.sqlite_path = self.data_dir / 'price_history.sqlite'
        self._ensure_schema()

    def append_prices(self, analyses: list[TickerAnalysis]) -> None:
        rows = build_price_history_rows(analyses)
        self._upsert_price_rows(rows)
        append_price_history_csv(self.csv_path, analyses)

    def upsert_collected_prices(
        self,
        collected: dict[str, CollectedTickerData],
        run_date: date,
    ) -> None:
        rows = build_price_rows_from_collected(collected, run_date)
        self._upsert_price_rows(rows)
        from src.utils.datastore_csv import _write_price_rows

        _write_price_rows(self.csv_path, rows)

    def append_analysis_snapshots(self, analyses: list[TickerAnalysis]) -> None:
        if not analyses:
            return
        rows = [
            (
                analysis.date,
                analysis.ticker,
                analysis.name,
                analysis.summary,
                analysis.signal_or_takeaway,
                str(analysis.news_tone.get('label', 'neutral')),
                _coerce_float_or_none(analysis.news_tone.get('score')),
                _coerce_float_or_none(analysis.news_tone.get('confidence')),
                str(analysis.news_tone.get('reasoning', '')),
                json.dumps(analysis.trade_frame, ensure_ascii=False),
            )
            for analysis in analyses
        ]
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.executemany(
                '''
                INSERT OR REPLACE INTO ticker_analysis_snapshots (
                    date,
                    ticker,
                    name,
                    summary,
                    signal_or_takeaway,
                    news_tone_label,
                    news_tone_score,
                    news_tone_confidence,
                    news_tone_reasoning,
                    trade_frame_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                rows,
            )
            connection.commit()
        finally:
            connection.close()

    def record_signals(
        self,
        analyses: list[TickerAnalysis],
        run_date: date,
        price_lookup: dict[str, float],
        *,
        decisions: list[Any] | None = None,
        market_regime: Any | None = None,
    ) -> None:
        super().record_signals(
            analyses,
            run_date,
            price_lookup,
            decisions=decisions,
            market_regime=market_regime,
        )
        self.sync_signal_history(self.signal_csv_path)

    def update_signal_returns(
        self,
        run_date: date,
        price_lookup: dict[str, float],
        *,
        price_history_rows: list[dict[str, str]] | None = None,
    ) -> int:
        updated = super().update_signal_returns(
            run_date,
            price_lookup,
            price_history_rows=price_history_rows,
        )
        self.sync_signal_history(self.signal_csv_path)
        return updated

    def sync_signal_history(self, csv_path: Path) -> None:
        rows = load_signal_rows(csv_path)
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.execute('DELETE FROM signal_history')
            connection.executemany(
                '''
                INSERT INTO signal_history (
                    signal_date,
                    ticker,
                    signal_type,
                    signal_direction,
                    llm_direction,
                    signal_price,
                    catalyst_tag,
                    news_tone,
                    trade_frame_scenario,
                    return_1d,
                    return_5d,
                    return_20d,
                    evaluated_1d,
                    evaluated_5d,
                    evaluated_20d
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    (
                        row.get('signal_date', ''),
                        str(row.get('ticker', '')).strip().upper(),
                        row.get('signal_type', ''),
                        row.get('signal_direction', ''),
                        row.get('llm_direction', ''),
                        row.get('signal_price', ''),
                        row.get('catalyst_tag', ''),
                        row.get('news_tone', ''),
                        row.get('trade_frame_scenario', ''),
                        row.get('return_1d', ''),
                        row.get('return_5d', ''),
                        row.get('return_20d', ''),
                        row.get('evaluated_1d', ''),
                        row.get('evaluated_5d', ''),
                        row.get('evaluated_20d', ''),
                    )
                    for row in rows
                ],
            )
            connection.commit()
        finally:
            connection.close()

    def record_analysis_run(self, *, run_date: date, success: bool, logger: Any | None = None) -> None:
        logger = logger or {}
        analyzer_quality = getattr(logger, 'analyzer_quality', {}) or {}
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.execute(
                '''
                INSERT OR REPLACE INTO analysis_runs (
                    run_date,
                    success,
                    daily_api_cost_usd,
                    models_used_json,
                    llm_usage_json,
                    batch_count,
                    fallback_count,
                    validation_failure_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    run_date.isoformat(),
                    1 if success else 0,
                    round(float(getattr(logger, 'daily_api_cost_usd', 0.0) or 0.0), 8),
                    json.dumps(dict(getattr(logger, 'models_used', {}) or {}), ensure_ascii=False),
                    json.dumps(dict(getattr(logger, 'llm_usage', {}) or {}), ensure_ascii=False),
                    int(analyzer_quality.get('batch_count', 0) or 0),
                    int(analyzer_quality.get('full_fallback_count', 0) or 0),
                    int(analyzer_quality.get('validation_failure_count', 0) or 0),
                ),
            )
            connection.commit()
        finally:
            connection.close()

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
        query = f'''
            SELECT
                date,
                ticker,
                price,
                daily_change,
                market_cap,
                trailing_pe,
                eps,
                high_52w,
                low_52w,
                open,
                high,
                low,
                close,
                volume
            FROM prices
            {where_clause}
            ORDER BY date, ticker
        '''
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
                    'open': row[9],
                    'high': row[10],
                    'low': row[11],
                    'close': row[12],
                    'volume': row[13],
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

    def get_ticker_history(self, ticker: str, *, limit: int = 90) -> list[dict[str, Any]]:
        normalized = ticker.strip().upper()
        if not normalized or limit <= 0:
            return []
        connection = sqlite3.connect(self.sqlite_path)
        try:
            cursor = connection.execute(
                '''
                SELECT
                    date,
                    ticker,
                    name,
                    summary,
                    signal_or_takeaway,
                    news_tone_label,
                    news_tone_score,
                    news_tone_confidence,
                    news_tone_reasoning,
                    trade_frame_json
                FROM ticker_analysis_snapshots
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT ?
                ''',
                (normalized, limit),
            )
            history: list[dict[str, Any]] = []
            for row in cursor.fetchall():
                history.append(
                    {
                        'date': row[0],
                        'ticker': row[1],
                        'name': row[2],
                        'summary': row[3],
                        'signal_or_takeaway': row[4],
                        'news_tone': {
                            'label': row[5],
                            'score': row[6],
                            'confidence': row[7],
                            'reasoning': row[8],
                        },
                        'trade_frame': _safe_load_json(row[9], default={}),
                    }
                )
            return history
        finally:
            connection.close()

    def get_signal_stats(self) -> dict[str, Any] | None:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            cursor = connection.execute(
                '''
                SELECT
                    signal_date,
                    ticker,
                    signal_type,
                    signal_direction,
                    llm_direction,
                    signal_price,
                    catalyst_tag,
                    news_tone,
                    trade_frame_scenario,
                    return_1d,
                    return_5d,
                    return_20d,
                    evaluated_1d,
                    evaluated_5d,
                    evaluated_20d
                FROM signal_history
                ORDER BY signal_date DESC, ticker ASC
                '''
            )
            rows = [
                {
                    'signal_date': row[0],
                    'ticker': row[1],
                    'signal_type': row[2],
                    'signal_direction': row[3],
                    'llm_direction': row[4],
                    'signal_price': row[5],
                    'catalyst_tag': row[6],
                    'news_tone': row[7],
                    'trade_frame_scenario': row[8],
                    'return_1d': row[9],
                    'return_5d': row[10],
                    'return_20d': row[11],
                    'evaluated_1d': row[12],
                    'evaluated_5d': row[13],
                    'evaluated_20d': row[14],
                }
                for row in cursor.fetchall()
            ]
        finally:
            connection.close()
        if not rows:
            return None
        return build_signal_stats_from_rows(rows)

    def load_signal_rows_data(self) -> list[dict[str, str]]:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            cursor = connection.execute(
                '''
                SELECT
                    signal_date,
                    ticker,
                    signal_type,
                    signal_direction,
                    llm_direction,
                    signal_price,
                    catalyst_tag,
                    news_tone,
                    trade_frame_scenario,
                    return_1d,
                    return_5d,
                    return_20d,
                    evaluated_1d,
                    evaluated_5d,
                    evaluated_20d
                FROM signal_history
                ORDER BY signal_date DESC, ticker ASC
                '''
            )
            return [
                {
                    'signal_date': row[0],
                    'ticker': row[1],
                    'signal_type': row[2],
                    'signal_direction': row[3],
                    'llm_direction': row[4],
                    'signal_price': row[5],
                    'catalyst_tag': row[6],
                    'news_tone': row[7],
                    'trade_frame_scenario': row[8],
                    'return_1d': row[9],
                    'return_5d': row[10],
                    'return_20d': row[11],
                    'evaluated_1d': row[12],
                    'evaluated_5d': row[13],
                    'evaluated_20d': row[14],
                }
                for row in cursor.fetchall()
            ]
        finally:
            connection.close()

    def get_analysis_quality(self, *, limit: int = 30) -> list[dict[str, Any]]:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            cursor = connection.execute(
                '''
                SELECT
                    run_date,
                    success,
                    daily_api_cost_usd,
                    models_used_json,
                    llm_usage_json,
                    batch_count,
                    fallback_count,
                    validation_failure_count
                FROM analysis_runs
                ORDER BY run_date DESC
                LIMIT ?
                ''',
                (limit,),
            )
            return [
                {
                    'run_date': row[0],
                    'success': bool(row[1]),
                    'daily_api_cost_usd': row[2],
                    'models_used': _safe_load_json(row[3], default={}),
                    'llm_usage': _safe_load_json(row[4], default={}),
                    'batch_count': row[5],
                    'fallback_count': row[6],
                    'validation_failure_count': row[7],
                }
                for row in cursor.fetchall()
            ]
        finally:
            connection.close()

    def get_peer_selection_cache(self, ticker: str, month_key: str) -> dict[str, Any] | None:
        normalized = ticker.strip().upper()
        if not normalized or not month_key:
            return None
        connection = sqlite3.connect(self.sqlite_path)
        try:
            cursor = connection.execute(
                '''
                SELECT payload_json
                FROM peer_selection_cache
                WHERE ticker = ? AND month_key = ?
                ''',
                (normalized, month_key),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return _safe_load_json(row[0], default=None)
        finally:
            connection.close()

    def set_peer_selection_cache(self, ticker: str, month_key: str, payload: dict[str, Any]) -> None:
        normalized = ticker.strip().upper()
        if not normalized or not month_key:
            return
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.execute(
                '''
                INSERT OR REPLACE INTO peer_selection_cache (
                    month_key,
                    ticker,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?)
                ''',
                (
                    month_key,
                    normalized,
                    json.dumps(payload, ensure_ascii=False),
                    date.today().isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

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
                    open TEXT NOT NULL DEFAULT 'N/A',
                    high TEXT NOT NULL DEFAULT 'N/A',
                    low TEXT NOT NULL DEFAULT 'N/A',
                    close TEXT NOT NULL DEFAULT 'N/A',
                    volume TEXT NOT NULL DEFAULT 'N/A',
                    PRIMARY KEY (date, ticker)
                )
                '''
            )
            self._ensure_price_columns(connection)
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS signal_history (
                    signal_date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    signal_direction TEXT NOT NULL,
                    llm_direction TEXT NOT NULL DEFAULT '',
                    signal_price TEXT NOT NULL,
                    catalyst_tag TEXT NOT NULL,
                    news_tone TEXT NOT NULL,
                    trade_frame_scenario TEXT NOT NULL,
                    return_1d TEXT NOT NULL,
                    return_5d TEXT NOT NULL,
                    return_20d TEXT NOT NULL,
                    evaluated_1d TEXT NOT NULL,
                    evaluated_5d TEXT NOT NULL,
                    evaluated_20d TEXT NOT NULL,
                    PRIMARY KEY (signal_date, ticker, signal_direction, catalyst_tag)
                )
                '''
            )
            self._ensure_signal_history_columns(connection)
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_date TEXT PRIMARY KEY,
                    success INTEGER NOT NULL,
                    daily_api_cost_usd REAL NOT NULL DEFAULT 0,
                    models_used_json TEXT NOT NULL DEFAULT '{}',
                    llm_usage_json TEXT NOT NULL DEFAULT '{}',
                    batch_count INTEGER NOT NULL DEFAULT 0,
                    fallback_count INTEGER NOT NULL DEFAULT 0,
                    validation_failure_count INTEGER NOT NULL DEFAULT 0
                )
                '''
            )
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS ticker_analysis_snapshots (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    name TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    signal_or_takeaway TEXT NOT NULL,
                    news_tone_label TEXT NOT NULL DEFAULT 'neutral',
                    news_tone_score REAL,
                    news_tone_confidence REAL,
                    news_tone_reasoning TEXT NOT NULL DEFAULT '',
                    trade_frame_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (date, ticker)
                )
                '''
            )
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS peer_selection_cache (
                    month_key TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (month_key, ticker)
                )
                '''
            )
            connection.commit()
        finally:
            connection.close()

    def _ensure_price_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in connection.execute("PRAGMA table_info(prices)").fetchall()
        }
        for column_name, column_spec in PRICE_COLUMN_DEFAULTS.items():
            if column_name in existing_columns:
                continue
            connection.execute(f'ALTER TABLE prices ADD COLUMN "{column_name}" {column_spec}')

    def _ensure_signal_history_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in connection.execute("PRAGMA table_info(signal_history)").fetchall()
        }
        if "llm_direction" not in existing_columns:
            connection.execute('ALTER TABLE signal_history ADD COLUMN "llm_direction" TEXT NOT NULL DEFAULT \'\'')

    def _upsert_price_rows(self, rows: list[dict[str, str]]) -> None:
        if not rows:
            return
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.executemany(
                '''
                INSERT OR REPLACE INTO prices (
                    date,
                    ticker,
                    price,
                    daily_change,
                    market_cap,
                    trailing_pe,
                    eps,
                    high_52w,
                    low_52w,
                    open,
                    high,
                    low,
                    close,
                    volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        row.get('open', 'N/A'),
                        row.get('high', 'N/A'),
                        row.get('low', 'N/A'),
                        row.get('close', 'N/A'),
                        row.get('volume', 'N/A'),
                    )
                    for row in rows
                ],
            )
            connection.commit()
        finally:
            connection.close()


def _safe_load_json(raw_value: str | None, *, default: Any) -> Any:
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return default


def _coerce_float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
