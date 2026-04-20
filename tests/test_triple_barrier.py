"""Tests for src.decision.triple_barrier — Phase A Task 2."""
from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from src.decision.triple_barrier import (
    build_ohlc_series,
    label_signal,
    summarize_barrier_outcomes,
)
from src.utils.signal_tracker import FIELDNAMES, update_triple_barrier_labels


def _bars(start: date, highs: list[float], lows: list[float], closes: list[float]) -> list[tuple[date, float, float, float]]:
    return [
        (start + timedelta(days=i), h, l, c)
        for i, (h, l, c) in enumerate(zip(highs, lows, closes, strict=True))
    ]


class TestLabelSignalBull(unittest.TestCase):
    def test_bull_hits_tp_before_stop(self) -> None:
        # signal @ 100, tp=3%=103, sl=2%=98
        # day 1: high=101 low=99 — neither touched
        # day 2: high=104 low=100 — tp hit
        bars = _bars(date(2025, 1, 2), [101, 104, 105], [99, 100, 100], [100, 103, 104])
        result = label_signal(
            signal_date=date(2025, 1, 1),
            signal_price=100.0,
            direction="bull",
            sessions=bars,
            horizon=20,
        )
        assert result is not None
        self.assertEqual(result["barrier_label"], "hit")
        self.assertEqual(result["barrier_hit_day"], "2")

    def test_bull_stops_before_tp(self) -> None:
        bars = _bars(date(2025, 1, 2), [101, 102, 102], [99, 97, 96], [100, 98, 97])
        result = label_signal(
            signal_date=date(2025, 1, 1),
            signal_price=100.0,
            direction="bull",
            sessions=bars,
            horizon=20,
        )
        assert result is not None
        self.assertEqual(result["barrier_label"], "stop")
        self.assertEqual(result["barrier_hit_day"], "2")

    def test_bull_timeout_returns_close_based_return(self) -> None:
        # 5 bars neither barrier touched, horizon=5 → timeout
        bars = _bars(
            date(2025, 1, 2),
            [101, 101.5, 102, 102.5, 102],
            [99.5, 99, 99, 99.5, 99.8],
            [100.5, 101, 101.5, 102, 101.5],
        )
        result = label_signal(
            signal_date=date(2025, 1, 1),
            signal_price=100.0,
            direction="bull",
            sessions=bars,
            horizon=5,
        )
        assert result is not None
        self.assertEqual(result["barrier_label"], "timeout")
        # return ≈ +1.5%
        self.assertIn("+1.5", result["barrier_return"])

    def test_pending_when_no_barrier_and_horizon_not_reached(self) -> None:
        bars = _bars(date(2025, 1, 2), [101], [99.5], [100.5])
        result = label_signal(
            signal_date=date(2025, 1, 1),
            signal_price=100.0,
            direction="bull",
            sessions=bars,
            horizon=20,
        )
        self.assertIsNone(result)


class TestLabelSignalBear(unittest.TestCase):
    def test_bear_hit_on_downside(self) -> None:
        # bear signal: drop to -2% is a "hit"
        bars = _bars(date(2025, 1, 2), [101, 100], [99, 97.5], [100, 98])
        result = label_signal(
            signal_date=date(2025, 1, 1),
            signal_price=100.0,
            direction="bear",
            sessions=bars,
            horizon=10,
        )
        assert result is not None
        self.assertEqual(result["barrier_label"], "hit")
        self.assertTrue(result["barrier_return"].startswith("-"))


class TestSummarize(unittest.TestCase):
    def test_counts_and_hit_rate(self) -> None:
        rows = [
            {"barrier_label": "hit", "barrier_return": "+3.00%", "barrier_hit_day": "3"},
            {"barrier_label": "hit", "barrier_return": "+3.00%", "barrier_hit_day": "5"},
            {"barrier_label": "stop", "barrier_return": "-2.00%", "barrier_hit_day": "2"},
            {"barrier_label": "timeout", "barrier_return": "+0.50%", "barrier_hit_day": "20"},
            {"barrier_label": "pending", "barrier_return": "", "barrier_hit_day": ""},
        ]
        summary = summarize_barrier_outcomes(rows)
        self.assertEqual(summary["counts"]["hit"], 2)
        self.assertEqual(summary["counts"]["stop"], 1)
        self.assertEqual(summary["counts"]["timeout"], 1)
        self.assertEqual(summary["counts"]["pending"], 1)
        # resolved = 4, hit = 2 → hit_rate 0.5
        self.assertEqual(summary["hit_rate"], 0.5)


class TestBuildOHLC(unittest.TestCase):
    def test_skips_malformed_rows(self) -> None:
        rows = [
            {"ticker": "AAA", "date": "2025-01-01", "high": "10", "low": "9", "close": "9.5"},
            {"ticker": "AAA", "date": "bogus", "high": "11", "low": "10", "close": "10.5"},
            {"ticker": "AAA", "date": "2025-01-02", "high": "11", "low": "10", "close": "10.5"},
        ]
        result = build_ohlc_series(rows)
        self.assertEqual(len(result["AAA"]), 2)


class TestSignalTrackerIntegration(unittest.TestCase):
    def test_update_triple_barrier_labels_updates_pending_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "signal_tracker.csv"
            # Seed one pending bull signal at 100 on 2025-01-01.
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow({
                    "signal_date": "2025-01-01",
                    "ticker": "AAA",
                    "signal_type": "takeaway",
                    "signal_direction": "bull",
                    "signal_price": "100.00",
                    "catalyst_tag": "test",
                    "news_tone": "bullish",
                    "trade_frame_scenario": "",
                    "return_1d": "N/A",
                    "return_5d": "N/A",
                    "return_20d": "N/A",
                    "evaluated_1d": "False",
                    "evaluated_5d": "False",
                    "evaluated_20d": "False",
                    "barrier_label": "pending",
                    "barrier_hit_day": "",
                    "barrier_return": "",
                    "barrier_date": "",
                })

            price_rows = [
                {"ticker": "AAA", "date": "2025-01-02", "high": "101", "low": "99", "close": "100"},
                {"ticker": "AAA", "date": "2025-01-03", "high": "104", "low": "100", "close": "103"},
            ]
            updated = update_triple_barrier_labels(
                csv_path,
                date(2025, 1, 3),
                price_history_rows=price_rows,
            )
            self.assertEqual(updated, 1)

            with csv_path.open("r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["barrier_label"], "hit")
            self.assertEqual(rows[0]["barrier_hit_day"], "2")


if __name__ == "__main__":
    unittest.main()
