from __future__ import annotations

import sqlite3
from pathlib import Path

from src.utils.datastore_sqlite import (
    SIGNAL_HISTORY_COLUMNS,
    SIGNAL_HISTORY_COLUMN_DEFAULTS,
    SIGNAL_HISTORY_JSON_METADATA_COLUMNS,
)
from src.utils.signal_tracker import load_signal_rows


def migrate_signal_tracker(
    csv_path: Path | None = None,
    sqlite_path: Path | None = None,
) -> dict[str, int]:
    source_csv = csv_path or (Path('output') / 'data' / 'signal_tracker.csv')
    target_sqlite = sqlite_path or (Path('output') / 'data' / 'price_history.sqlite')
    target_sqlite.parent.mkdir(parents=True, exist_ok=True)

    rows = load_signal_rows(source_csv) if source_csv.exists() else []

    connection = sqlite3.connect(target_sqlite)
    try:
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
                conviction TEXT NOT NULL DEFAULT '',
                raw_conviction TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL DEFAULT '',
                regime TEXT NOT NULL DEFAULT '',
                sub_regime TEXT NOT NULL DEFAULT '',
                factors_json TEXT NOT NULL DEFAULT '{}',
                factor_reasoning_json TEXT NOT NULL DEFAULT '{}',
                confidence_meta_json TEXT NOT NULL DEFAULT '{}',
                return_1d TEXT NOT NULL,
                return_5d TEXT NOT NULL,
                return_20d TEXT NOT NULL,
                evaluated_1d TEXT NOT NULL,
                evaluated_5d TEXT NOT NULL,
                evaluated_20d TEXT NOT NULL,
                barrier_label TEXT NOT NULL DEFAULT 'pending',
                barrier_hit_day TEXT NOT NULL DEFAULT '',
                barrier_return TEXT NOT NULL DEFAULT '',
                barrier_date TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (signal_date, ticker, signal_direction, catalyst_tag)
            )
            '''
        )
        _ensure_signal_history_columns(connection)
        connection.execute('DELETE FROM signal_history')
        columns_sql = ', '.join(SIGNAL_HISTORY_COLUMNS)
        placeholders = ', '.join('?' for _ in SIGNAL_HISTORY_COLUMNS)
        connection.executemany(
            f'''
            INSERT INTO signal_history ({columns_sql})
            VALUES ({placeholders})
            ''',
            [
                tuple(
                    _signal_history_row_value(row, column_name)
                    for column_name in SIGNAL_HISTORY_COLUMNS
                )
                for row in rows
            ],
        )
        migrated_rows = int(
            connection.execute('SELECT COUNT(*) FROM signal_history').fetchone()[0]
        )
        connection.commit()
    finally:
        connection.close()

    return {'csv_rows': len(rows), 'sqlite_rows': migrated_rows}


def _ensure_signal_history_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        str(row[1]).strip().lower()
        for row in connection.execute("PRAGMA table_info(signal_history)").fetchall()
    }
    for column_name, column_spec in SIGNAL_HISTORY_COLUMN_DEFAULTS.items():
        if column_name in existing_columns:
            continue
        connection.execute(f'ALTER TABLE signal_history ADD COLUMN "{column_name}" {column_spec}')


def _signal_history_default_value(column_name: str) -> str:
    if column_name in SIGNAL_HISTORY_JSON_METADATA_COLUMNS:
        return '{}'
    if column_name == 'barrier_label':
        return 'pending'
    column_spec = SIGNAL_HISTORY_COLUMN_DEFAULTS.get(column_name, '')
    if "DEFAULT 'N/A'" in column_spec:
        return 'N/A'
    return ''


def _signal_history_row_value(row: dict[str, str], column_name: str) -> str:
    if column_name == 'ticker':
        return str(row.get(column_name, '')).strip().upper()
    value = row.get(column_name, _signal_history_default_value(column_name))
    if column_name in SIGNAL_HISTORY_JSON_METADATA_COLUMNS and not str(value).strip():
        return '{}'
    return str(value)


if __name__ == '__main__':
    result = migrate_signal_tracker()
    print(result)
