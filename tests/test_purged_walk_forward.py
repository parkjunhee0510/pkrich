"""Tests for purged walk-forward validation (Phase A Task 3)."""
from __future__ import annotations

import json
import random
import unittest
from datetime import date, timedelta

from src.decision.tune_weights import (
    EMBARGO_DAYS_DEFAULT,
    PURGE_HORIZON_DEFAULT,
    _purge_training_set,
    build_tuning_payload,
    purged_walk_forward_grid_search,
)


def _make_row(
    *,
    signal_date: date,
    regime: str,
    factors: dict[str, float],
    ret5: float,
) -> dict[str, str]:
    return {
        "signal_date": signal_date.isoformat(),
        "regime": regime,
        "factors_json": json.dumps(factors),
        "evaluated_5d": "True",
        "return_5d": f"{ret5:+.2f}%",
    }


def _synthetic_signal_history(n: int, *, start: date, seed: int = 11) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for i in range(n):
        factors = {
            "momentum": rng.uniform(-1, 1),
            "valuation": rng.uniform(-1, 1),
            "signal_track_record": rng.uniform(-1, 1),
            "catalyst_recency": rng.uniform(-1, 1),
            "news_tone": rng.uniform(-1, 1),
        }
        # momentum drives 5D return.
        ret5 = 2.5 * factors["momentum"] + rng.uniform(-1.0, 1.0)
        rows.append(
            _make_row(
                signal_date=start + timedelta(days=i),
                regime="risk_on",
                factors=factors,
                ret5=ret5,
            )
        )
    return rows


class TestPurgeTrainingSet(unittest.TestCase):
    def test_overlapping_rows_removed(self) -> None:
        dated: list[tuple[str, dict[str, float], float]] = [
            # overlaps: label 2025-01-03→08 vs test window 2025-01-05→10
            ("2025-01-03", {"momentum": 0.1}, 1.0),
            # overlaps via embargo (2025-01-04 + 5 = 2025-01-09, test_start=2025-01-05)
            ("2025-01-04", {"momentum": 0.1}, 1.0),
            # safe: label ends 2025-01-01 well before embargo window
            ("2024-12-20", {"momentum": 0.2}, 2.0),
            # safe: starts after test_end + embargo
            ("2025-02-10", {"momentum": 0.3}, 3.0),
        ]
        kept = _purge_training_set(
            dated,
            test_start=date(2025, 1, 5),
            test_end=date(2025, 1, 10),
            horizon_days=5,
            embargo_days=5,
        )
        self.assertEqual(len(kept), 2)

    def test_malformed_date_dropped(self) -> None:
        dated = [("not-a-date", {"momentum": 0.5}, 1.0)]
        kept = _purge_training_set(
            dated,
            test_start=date(2025, 1, 1),
            test_end=date(2025, 1, 5),
            horizon_days=5,
            embargo_days=5,
        )
        self.assertEqual(kept, [])


class TestPurgedWalkForward(unittest.TestCase):
    def test_insufficient_data_flag(self) -> None:
        rows = _synthetic_signal_history(5, start=date(2025, 1, 1))
        report = purged_walk_forward_grid_search(rows)
        risk_on = report["regimes"]["risk_on"]
        self.assertEqual(risk_on["status"], "insufficient_data")

    def test_purged_folds_report_purge_count(self) -> None:
        rows = _synthetic_signal_history(200, start=date(2025, 1, 1))
        report = purged_walk_forward_grid_search(
            rows, horizon=5, n_folds=3, embargo_days=5
        )
        risk_on = report["regimes"]["risk_on"]
        self.assertEqual(risk_on["status"], "ok")
        # At least one fold must report a positive purge count when data
        # is contiguous and horizon+embargo > 0.
        valid_folds = [f for f in risk_on["folds"] if f.get("status") == "ok"]
        self.assertGreaterEqual(len(valid_folds), 2)
        total_purged = sum(f["purged"] for f in valid_folds)
        self.assertGreater(total_purged, 0)

    def test_overfit_gap_in_sample_higher_or_equal(self) -> None:
        rows = _synthetic_signal_history(200, start=date(2025, 1, 1))
        report = purged_walk_forward_grid_search(rows, horizon=5, n_folds=3)
        risk_on = report["regimes"]["risk_on"]
        self.assertEqual(risk_on["status"], "ok")
        # In-sample Spearman (leaky) is grid-search optimized, so it should
        # be >= OOS mean Spearman on well-generated synthetic data.
        ins = risk_on["in_sample_spearman_leaky"]
        oos_mean = risk_on["oos_spearman_mean"]
        self.assertIsNotNone(ins)
        self.assertIsNotNone(oos_mean)
        self.assertGreaterEqual(ins, oos_mean - 0.05)  # small tolerance


class TestBuildTuningPayloadIncludesPurged(unittest.TestCase):
    def test_payload_contains_purged_walk_forward(self) -> None:
        rows = _synthetic_signal_history(60, start=date(2025, 1, 1))
        payload = build_tuning_payload(rows, horizon=5)
        self.assertIn("purged_walk_forward", payload)
        self.assertIn("regimes", payload["purged_walk_forward"])

    def test_defaults_match_lopez_de_prado_convention(self) -> None:
        self.assertEqual(PURGE_HORIZON_DEFAULT, 5)
        self.assertEqual(EMBARGO_DAYS_DEFAULT, 5)


if __name__ == "__main__":
    unittest.main()
