from __future__ import annotations

import sqlite3
from pathlib import Path

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
        connection.execute('DELETE FROM signal_history')
        connection.executemany(
            '''
            INSERT INTO signal_history (
                signal_date, ticker, signal_type, signal_direction, signal_price,
                catalyst_tag, news_tone, trade_frame_scenario,
                return_1d, return_5d, return_20d,
                evaluated_1d, evaluated_5d, evaluated_20d
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    row.get('signal_date', ''),
                    str(row.get('ticker', '')).strip().upper(),
                    row.get('signal_type', ''),
                    row.get('signal_direction', ''),
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
        migrated_rows = int(
            connection.execute('SELECT COUNT(*) FROM signal_history').fetchone()[0]
        )
        connection.commit()
    finally:
        connection.close()

    return {'csv_rows': len(rows), 'sqlite_rows': migrated_rows}


if __name__ == '__main__':
    result = migrate_signal_tracker()
    print(result)
