"""Tests for the sector explorer collector + JSON exporter.

Stubs out yfinance and the RSS news collector so the test stays offline.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from src.collector.sector_scan import (
    SectorSnapshot,
    SectorTickerSnapshot,
    SectorPricePoint,
    scan_sectors,
)
from src.output.sectors_json import write_sectors_json
from src.utils.config import SectorConfig, SectorTickerConfig


class _FakeHistory:
    """Mimics the DataFrame shape used by _fetch_yfinance_snapshot."""

    def __init__(self, rows: list[tuple[str, float]]):
        self._rows = rows

    def iterrows(self):
        for iso, close in self._rows:
            class _Index:
                def __init__(self, iso_inner: str): self._iso = iso_inner
                def date(self): return date.fromisoformat(self._iso)

            yield _Index(iso), {"Close": close}


class _FakeTicker:
    def __init__(self, rows):
        self._rows = rows
        self.info = {"currency": "USD"}

    def history(self, **_kwargs):
        return _FakeHistory(self._rows)


class SectorScanTests(unittest.TestCase):
    def setUp(self):
        # Stub yfinance module so _fetch_yfinance_snapshot can import it.
        self._yf_rows = [("2025-01-01", 100.0), ("2025-01-02", 102.0)]
        fake_yf = mock.MagicMock()
        fake_yf.Ticker.return_value = _FakeTicker(self._yf_rows)
        self._yf_patcher = mock.patch.dict(sys.modules, {"yfinance": fake_yf})
        self._yf_patcher.start()

        # Force "external_enabled + yfinance_ready" path.
        self._env_patcher = mock.patch(
            "src.collector.sector_scan.is_env_flag_enabled", return_value=True
        )
        self._env_patcher.start()
        self._tcp_patcher = mock.patch(
            "src.collector.sector_scan.can_open_tcp_connection", return_value=True
        )
        self._tcp_patcher.start()

        # Short-circuit news collection.
        self._news_patcher = mock.patch(
            "src.collector.news_rss._collect_rss_news", return_value=[]
        )
        self._news_patcher.start()

    def tearDown(self):
        self._yf_patcher.stop()
        self._env_patcher.stop()
        self._tcp_patcher.stop()
        self._news_patcher.stop()

    def _sample_config(self, *, benchmark: str = "") -> SectorConfig:
        return SectorConfig(
            id="space",
            name="우주",
            description="Space sector",
            news_keywords=["space", "launch"],
            tickers=[
                SectorTickerConfig(ticker="RKLB", name="Rocket Lab"),
                SectorTickerConfig(ticker="PL", name="Planet Labs"),
            ],
            benchmark_etf=benchmark,
        )

    def test_scan_populates_price_and_history(self):
        result = scan_sectors([self._sample_config()], date(2025, 1, 2))
        self.assertEqual(len(result), 1)
        snapshot = result[0]
        self.assertEqual(snapshot.id, "space")
        self.assertEqual(len(snapshot.tickers), 2)
        rkl = snapshot.tickers[0]
        self.assertEqual(rkl.ticker, "RKLB")
        self.assertEqual(rkl.currency, "USD")
        self.assertTrue(rkl.price.startswith("102.00"))
        self.assertEqual(rkl.change_percent, "+2.00%")
        self.assertEqual(len(rkl.history), 2)
        self.assertEqual(rkl.history[-1].close, 102.0)

    def test_benchmark_etf_fetched_and_attached(self):
        result = scan_sectors(
            [self._sample_config(benchmark="UFO")], date(2025, 1, 2)
        )
        snapshot = result[0]
        self.assertIsNotNone(snapshot.benchmark)
        self.assertEqual(snapshot.benchmark.ticker, "UFO")  # type: ignore[union-attr]
        self.assertEqual(len(snapshot.benchmark.history), 2)  # type: ignore[union-attr]

    def test_benchmark_absent_when_unconfigured(self):
        result = scan_sectors([self._sample_config()], date(2025, 1, 2))
        self.assertIsNone(result[0].benchmark)

    def test_skip_tickers_emits_sentinel_without_calling_yfinance(self):
        result = scan_sectors(
            [self._sample_config()],
            date(2025, 1, 2),
            skip_tickers={"RKLB"},
        )
        rkl = result[0].tickers[0]
        self.assertEqual(rkl.error, "reuse_from_watchlist")
        self.assertEqual(rkl.price, "")

    def test_write_sectors_json_roundtrip(self):
        snapshot = SectorSnapshot(
            id="space",
            name="우주",
            description="Space sector",
            tickers=[
                SectorTickerSnapshot(
                    ticker="RKLB",
                    name="Rocket Lab",
                    price="102.00 USD",
                    currency="USD",
                    change_percent="+2.00%",
                    history=[SectorPricePoint(date="2025-01-02", close=102.0)],
                    news=[],
                )
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = write_sectors_json(
                [snapshot], date(2025, 1, 2), output_root=Path(tmp)
            )
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["updated_at"], "2025-01-02")
            self.assertEqual(payload["sectors"][0]["id"], "space")
            self.assertEqual(
                payload["sectors"][0]["tickers"][0]["price"], "102.00 USD"
            )


if __name__ == "__main__":
    unittest.main()
