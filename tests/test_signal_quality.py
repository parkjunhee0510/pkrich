"""Tests for src.decision.signal_quality — Phase A measurement module."""
from __future__ import annotations

import json
import random
import unittest
from datetime import date, timedelta

from src.decision.signal_quality import (
    build_signal_quality_payload,
    compute_ic_decay,
    compute_kelly_fractions,
    compute_rolling_ic,
    compute_signal_turnover,
)


def _make_row(
    *,
    signal_date: date,
    ticker: str,
    direction: str,
    factors: dict[str, float],
    returns: dict[int, float],
) -> dict[str, str]:
    row: dict[str, str] = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "signal_direction": direction,
        "factors_json": json.dumps(factors),
    }
    for horizon, ret in returns.items():
        row[f"return_{horizon}d"] = f"{ret:+.2f}%"
        row[f"evaluated_{horizon}d"] = "True"
    for horizon in (1, 5, 20):
        row.setdefault(f"evaluated_{horizon}d", "False")
        row.setdefault(f"return_{horizon}d", "N/A")
    return row


def _synthetic_rows(n: int, *, start: date, seed: int = 7) -> list[dict[str, str]]:
    """Build `n` rows where factor `momentum` predicts 5D return positively."""
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for i in range(n):
        mom = rng.uniform(-1.0, 1.0)
        noise = rng.uniform(-1.5, 1.5)
        ret5 = 3.0 * mom + noise  # correlated with mom
        ret1 = 1.0 * mom + rng.uniform(-0.8, 0.8)
        ret20 = 0.5 * mom + rng.uniform(-2.5, 2.5)
        direction = "bull" if mom > 0 else "bear"
        rows.append(
            _make_row(
                signal_date=start + timedelta(days=i),
                ticker=f"T{i % 5}",
                direction=direction,
                factors={"momentum": mom, "noise_factor": rng.uniform(-1, 1)},
                returns={1: ret1, 5: ret5, 20: ret20},
            )
        )
    return rows


class TestICDecay(unittest.TestCase):
    def test_insufficient_data_flag(self) -> None:
        rows = _synthetic_rows(3, start=date(2025, 1, 1))
        payload = compute_ic_decay(rows)
        self.assertEqual(payload["status"], "insufficient_data")
        self.assertEqual(payload["factors"], [])

    def test_momentum_factor_ic_present(self) -> None:
        rows = _synthetic_rows(80, start=date(2025, 1, 1))
        payload = compute_ic_decay(rows)
        self.assertEqual(payload["status"], "ok")
        momentum = next(f for f in payload["factors"] if f["factor"] == "momentum")
        # momentum was constructed to correlate with returns
        self.assertIsNotNone(momentum["ic"]["5d"])
        self.assertGreater(abs(momentum["ic"]["5d"]), 0.2)


class TestRollingIC(unittest.TestCase):
    def test_insufficient_data(self) -> None:
        rows = _synthetic_rows(5, start=date(2025, 1, 1))
        payload = compute_rolling_ic(rows)
        self.assertEqual(payload["status"], "insufficient_data")

    def test_series_emits_chronological_points(self) -> None:
        rows = _synthetic_rows(200, start=date(2025, 1, 1))
        payload = compute_rolling_ic(rows, horizon=5, window_days=60, step_days=15)
        self.assertEqual(payload["status"], "ok")
        momentum = next(
            (f for f in payload["factors"] if f["factor"] == "momentum"), None
        )
        self.assertIsNotNone(momentum)
        series = momentum["series"]
        self.assertGreater(len(series), 1)
        dates = [p["window_end"] for p in series]
        self.assertEqual(dates, sorted(dates))


class TestKellyFractions(unittest.TestCase):
    def test_bull_direction_positive_kelly(self) -> None:
        rows: list[dict[str, str]] = []
        # 30 bull signals, 70% hit rate, payoff 2:1
        for i in range(30):
            win = i % 10 < 7
            ret = 2.0 if win else -1.0
            rows.append(
                _make_row(
                    signal_date=date(2025, 1, 1) + timedelta(days=i),
                    ticker=f"T{i}",
                    direction="bull",
                    factors={"momentum": 0.5},
                    returns={5: ret},
                )
            )
        payload = compute_kelly_fractions(rows, horizon=5)
        bull = payload["by_direction"]["bull"]
        self.assertEqual(bull["status"], "ok")
        self.assertAlmostEqual(bull["hit_rate"], 0.7, places=2)
        self.assertGreater(bull["kelly_half"], 0.0)
        self.assertLessEqual(bull["kelly_half"], 0.5)

    def test_too_few_rows_marks_insufficient(self) -> None:
        rows = [
            _make_row(
                signal_date=date(2025, 1, 1) + timedelta(days=i),
                ticker="A",
                direction="bull",
                factors={"x": 0.1},
                returns={5: 1.0},
            )
            for i in range(3)
        ]
        payload = compute_kelly_fractions(rows, horizon=5)
        self.assertEqual(payload["by_direction"]["bull"]["status"], "insufficient_data")


class TestSignalTurnover(unittest.TestCase):
    def test_identical_sets_zero_turnover(self) -> None:
        rows = [
            _make_row(
                signal_date=date(2025, 1, 1),
                ticker="AAPL",
                direction="bull",
                factors={},
                returns={},
            ),
            _make_row(
                signal_date=date(2025, 1, 2),
                ticker="AAPL",
                direction="bull",
                factors={},
                returns={},
            ),
        ]
        payload = compute_signal_turnover(rows)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["points"][0]["turnover"], 0.0)

    def test_disjoint_sets_full_turnover(self) -> None:
        rows = [
            _make_row(
                signal_date=date(2025, 1, 1),
                ticker="AAPL",
                direction="bull",
                factors={},
                returns={},
            ),
            _make_row(
                signal_date=date(2025, 1, 2),
                ticker="MSFT",
                direction="bull",
                factors={},
                returns={},
            ),
        ]
        payload = compute_signal_turnover(rows)
        self.assertEqual(payload["points"][0]["turnover"], 1.0)


class TestPayloadShape(unittest.TestCase):
    def test_payload_includes_all_panels(self) -> None:
        rows = _synthetic_rows(80, start=date(2025, 1, 1))
        payload = build_signal_quality_payload(rows)
        self.assertIn("ic_decay", payload)
        self.assertIn("rolling_ic", payload)
        self.assertIn("kelly", payload)
        self.assertIn("turnover", payload)


if __name__ == "__main__":
    unittest.main()
