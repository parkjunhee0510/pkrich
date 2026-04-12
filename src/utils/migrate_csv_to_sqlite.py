from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def migrate_csv_to_sqlite(
    csv_path: Path | None = None,
    sqlite_path: Path | None = None,
) -> dict[str, int]:
    source_csv = csv_path or (Path('output') / 'data' / 'price_history.csv')
    target_sqlite = sqlite_path or (Path('output') / 'data' / 'price_history.sqlite')
    target_sqlite.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if source_csv.exists():
        with source_csv.open('r', encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))

    connection = sqlite3.connect(target_sqlite)
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
                "open" TEXT NOT NULL DEFAULT 'N/A',
                high TEXT NOT NULL DEFAULT 'N/A',
                low TEXT NOT NULL DEFAULT 'N/A',
                "close" TEXT NOT NULL DEFAULT 'N/A',
                volume TEXT NOT NULL DEFAULT 'N/A',
                PRIMARY KEY (date, ticker)
            )
            '''
        )
        connection.execute('DELETE FROM prices')
        connection.executemany(
            '''
            INSERT OR REPLACE INTO prices (
                date, ticker, price, daily_change, market_cap, trailing_pe, eps,
                high_52w, low_52w, "open", high, low, "close", volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    row.get('date', ''),
                    row.get('ticker', ''),
                    row.get('price', 'N/A'),
                    row.get('daily_change', 'N/A'),
                    row.get('market_cap', 'N/A'),
                    row.get('trailing_pe', 'N/A'),
                    row.get('eps', 'N/A'),
                    row.get('52w_high', 'N/A'),
                    row.get('52w_low', 'N/A'),
                    row.get('open', 'N/A'),
                    row.get('high', 'N/A'),
                    row.get('low', 'N/A'),
                    row.get('close', 'N/A'),
                    row.get('volume', 'N/A'),
                )
                for row in rows
            ],
        )
        migrated_rows = int(connection.execute('SELECT COUNT(*) FROM prices').fetchone()[0])
        connection.commit()
    finally:
        connection.close()

    return {'csv_rows': len(rows), 'sqlite_rows': migrated_rows}


if __name__ == '__main__':
    result = migrate_csv_to_sqlite()
    print(result)
