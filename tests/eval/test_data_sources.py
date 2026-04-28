from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.eval.data_sources import AuditDataset, load_window


class TestLoadWindow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        ticker_dir = self.tmp / "output" / "data" / "tickers" / "AAPL" / "daily"
        ticker_dir.mkdir(parents=True)
        (ticker_dir / "2026-04-28.json").write_text(json.dumps({
            "schema_version": 1, "date": "2026-04-28", "ticker": "AAPL",
            "payload": {"ticker": "AAPL", "summary": "x", "key_news": [], "news_references": []}
        }))
        log_dir = self.tmp / "logs" / "pipeline"
        log_dir.mkdir(parents=True)
        (log_dir / "2026-04-28.summary.json").write_text(json.dumps({
            "date": "2026-04-28", "fallback_count": 0, "schema_retry_count": 0,
            "model_usage": {"per_ticker_tokens": {"AAPL": 3000}, "total_tokens": 3000},
            "daily_api_cost_usd": 0.10,
        }))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load_window_one_day(self):
        ds = load_window(
            root=self.tmp, end=date(2026, 4, 28), window_days=1,
            tickers=["AAPL"], model_profile="economy",
        )
        self.assertEqual(ds.tickers, ("AAPL",))
        self.assertIn(date(2026, 4, 28), ds.daily["AAPL"])
        self.assertEqual(ds.summaries[date(2026, 4, 28)]["fallback_count"], 0)

    def test_load_window_missing_day_is_none(self):
        ds = load_window(
            root=self.tmp, end=date(2026, 4, 28), window_days=2,
            tickers=["AAPL"], model_profile="economy",
        )
        self.assertEqual(len(ds.daily["AAPL"]), 1)


class TestAuditDatasetIsFrozen(unittest.TestCase):
    def test_frozen(self):
        ds = AuditDataset(
            window_start=date(2026, 4, 28), window_end=date(2026, 4, 28),
            tickers=("AAPL",), daily={}, logs=(), summaries={}, model_profile="economy",
        )
        with self.assertRaises(Exception):
            ds.tickers = ("MSFT",)  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
