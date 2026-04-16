"""Unit tests for src/collector/cache.py (SQLite ResponseCache)."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from src.collector.cache import CacheEntry, ResponseCache


class ResponseCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "cache.sqlite"
        self._cache = ResponseCache(self._db_path)

    def tearDown(self) -> None:
        self._cache.close()
        self._tmp.cleanup()

    def test_set_then_get_roundtrip(self) -> None:
        payload = {"price": 100.5, "market_cap": "2T"}
        self._cache.set("yfinance", "AAPL:2026-04-15", payload, ttl_hours=1.0)
        entry = self._cache.get("yfinance", "AAPL:2026-04-15")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.payload, payload)
        self.assertFalse(entry.is_stale)

    def test_get_missing_returns_none(self) -> None:
        self.assertIsNone(self._cache.get("yfinance", "missing"))

    def test_stale_entry_flag(self) -> None:
        self._cache.set("fmp", "NVDA:old", {"x": 1}, ttl_hours=0.0)
        # ttl=0 means any age > 0 is stale.
        time.sleep(0.01)
        entry = self._cache.get("fmp", "NVDA:old")
        self.assertIsNotNone(entry)
        self.assertTrue(entry.is_stale)

    def test_set_upserts_existing_key(self) -> None:
        self._cache.set("yf", "k", {"v": 1}, ttl_hours=1.0)
        self._cache.set("yf", "k", {"v": 2}, ttl_hours=1.0)
        entry = self._cache.get("yf", "k")
        self.assertEqual(entry.payload["v"], 2)

    def test_prune_deletes_old_entries(self) -> None:
        self._cache.set("yf", "fresh", {"v": "new"}, ttl_hours=1.0)
        # Backdate one row manually via the underlying connection.
        old_stored = time.time() - 8 * 86400
        self._cache._conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO provider_cache VALUES (?, ?, ?, ?, ?)",
            ("yf", "old", "{}", old_stored, 3600),
        )
        deleted = self._cache.prune_older_than(days=7.0)
        self.assertEqual(deleted, 1)
        self.assertIsNone(self._cache.get("yf", "old"))
        self.assertIsNotNone(self._cache.get("yf", "fresh"))

    def test_non_serializable_payload_does_not_crash(self) -> None:
        class NotSerializable:
            pass

        # default=str → falls back to repr. Should not raise.
        self._cache.set("yf", "k", {"obj": NotSerializable()}, ttl_hours=0.5)
        entry = self._cache.get("yf", "k")
        self.assertIsNotNone(entry)
        self.assertIsInstance(entry.payload["obj"], str)


class CacheEntryTests(unittest.TestCase):
    def test_is_stale_respects_ttl(self) -> None:
        fresh = CacheEntry(payload={}, stored_at=time.time() - 10, ttl_seconds=3600)
        stale = CacheEntry(payload={}, stored_at=time.time() - 10000, ttl_seconds=3600)
        self.assertFalse(fresh.is_stale)
        self.assertTrue(stale.is_stale)


if __name__ == "__main__":
    unittest.main()
