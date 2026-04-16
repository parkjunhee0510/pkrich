"""SQLite-backed cross-run response cache for data providers.

Purpose:
  * Persist API responses across pipeline runs so we don't re-hit
    rate-limited endpoints for stable data (fundamentals, SEC filings).
  * Return stale data as a graceful fallback when a live call fails.
  * Survive in GitHub Actions via the `output/data/api_cache.sqlite`
    artifact.

Schema (single table):
    provider      TEXT    Provider name (e.g. "yfinance")
    cache_key     TEXT    Logical key (e.g. "AAPL:price:2026-04-15")
    payload_json  TEXT    JSON-encoded response
    stored_at     REAL    Unix timestamp when written
    ttl_seconds   INTEGER Soft TTL; entries past this are `stale=True`
    PRIMARY KEY (provider, cache_key)

The cache never deletes on its own. `prune_older_than(days)` is exposed for
GitHub Actions to keep the sqlite file small.

Thread safety: sqlite3 with `check_same_thread=False` plus an internal lock.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("output/data/api_cache.sqlite")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS provider_cache (
    provider     TEXT NOT NULL,
    cache_key    TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    stored_at    REAL NOT NULL,
    ttl_seconds  INTEGER NOT NULL,
    PRIMARY KEY (provider, cache_key)
)
"""
_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_provider_cache_stored_at "
    "ON provider_cache(stored_at)"
)


@dataclass(frozen=True)
class CacheEntry:
    """Result of a cache lookup."""
    payload: Any
    stored_at: float
    ttl_seconds: int

    @property
    def age_seconds(self) -> float:
        return time.time() - self.stored_at

    @property
    def is_stale(self) -> bool:
        return self.age_seconds > self.ttl_seconds


class ResponseCache:
    """SQLite-backed cross-run cache.

    All methods are safe to call from multiple threads.
    Writes are serialized through an internal lock; reads are also locked
    because sqlite connection objects are not thread-safe.
    """

    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit — we don't need transactions
        )
        self._conn.execute(_SCHEMA_SQL)
        self._conn.execute(_INDEX_SQL)

    def get(self, provider: str, cache_key: str) -> CacheEntry | None:
        """Fetch a cache entry. Returns None if absent.

        Callers decide how to treat stale entries (CacheEntry.is_stale).
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json, stored_at, ttl_seconds "
                "FROM provider_cache WHERE provider = ? AND cache_key = ?",
                (provider, cache_key),
            ).fetchone()

        if row is None:
            return None

        payload_json, stored_at, ttl_seconds = row
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError) as err:
            logger.warning(
                "cache payload decode failed provider=%s key=%s err=%s",
                provider, cache_key, err,
            )
            return None

        return CacheEntry(
            payload=payload,
            stored_at=float(stored_at),
            ttl_seconds=int(ttl_seconds),
        )

    def set(
        self,
        provider: str,
        cache_key: str,
        payload: Any,
        ttl_hours: float,
    ) -> None:
        """Store a payload with a soft TTL (in hours)."""
        try:
            payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as err:
            logger.warning(
                "cache payload encode failed provider=%s key=%s err=%s",
                provider, cache_key, err,
            )
            return

        ttl_seconds = int(max(0.0, ttl_hours) * 3600)
        stored_at = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO provider_cache "
                "(provider, cache_key, payload_json, stored_at, ttl_seconds) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(provider, cache_key) DO UPDATE SET "
                "payload_json = excluded.payload_json, "
                "stored_at = excluded.stored_at, "
                "ttl_seconds = excluded.ttl_seconds",
                (provider, cache_key, payload_json, stored_at, ttl_seconds),
            )

    def prune_older_than(self, days: float) -> int:
        """Delete entries older than `days`. Returns deleted row count.

        Intended for scheduled maintenance (GitHub Actions artifact shrinking).
        """
        cutoff = time.time() - (days * 86400)
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM provider_cache WHERE stored_at < ?",
                (cutoff,),
            )
            return cursor.rowcount or 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # Context manager support for tests.
    def __enter__(self) -> "ResponseCache":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.close()


__all__ = ["ResponseCache", "CacheEntry"]
