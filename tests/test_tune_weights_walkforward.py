from __future__ import annotations

import json
import unittest
from datetime import date, timedelta

from src.decision.tune_weights import (
    WALKFORWARD_MIN_TEST_SIZE,
    WALKFORWARD_MIN_TRAIN_SIZE,
    build_tuning_payload,
    walk_forward_grid_search,
)


def _dated_row(
    *,
    signal_date: str,
    factors: dict[str, float],
    return_5d: float,
    regime: str = "risk_on",
    conviction: float = 60.0,
    evaluated: bool = True,
) -> dict[str, str]:
    return {
        "signal_date": signal_date,
        "factors_json": json.dumps(factors),
        "return_5d": f"{return_5d:+.2f}%",
        "evaluated_5d": "True" if evaluated else "False",
        "regime": regime,
        "conviction": f"{conviction:.1f}",
    }


def _build_series(n: int, *, regime: str, start_day: int = 0) -> list[dict[str, str]]:
    """momentum drives return, valuation anti-correlates — stable generator."""
    rows = []
    for i in range(n):
        d = date(2026, 1, 1) + timedelta(days=start_day + i)
        momentum = float(i % 20)
        valuation = float(20 - (i % 20))
        rows.append(
            _dated_row(
                signal_date=d.isoformat(),
                factors={"momentum": momentum, "valuation": valuation},
                return_5d=momentum * 0.1,
                regime=regime,
            )
        )
    return rows


class WalkForwardTests(unittest.TestCase):
    def test_insufficient_data_reports_status(self) -> None:
        rows = _build_series(10, regime="risk_on")
        result = walk_forward_grid_search(rows)
        self.assertEqual(result["regimes"]["risk_on"]["status"], "insufficient_data")
        self.assertIsNone(result["regimes"]["risk_on"]["oos_spearman_mean"])

    def test_sufficient_data_returns_folds_and_mean(self) -> None:
        n = WALKFORWARD_MIN_TRAIN_SIZE + 5 * WALKFORWARD_MIN_TEST_SIZE
        rows = _build_series(n, regime="risk_on")
        result = walk_forward_grid_search(rows, n_folds=3)
        regime_report = result["regimes"]["risk_on"]
        self.assertEqual(regime_report["status"], "ok")
        self.assertGreaterEqual(len(regime_report["folds"]), 2)
        self.assertIsNotNone(regime_report["oos_spearman_mean"])
        self.assertIsNotNone(regime_report["selected_multipliers"])

    def test_oos_spearman_positive_when_signal_is_real(self) -> None:
        n = WALKFORWARD_MIN_TRAIN_SIZE + 5 * WALKFORWARD_MIN_TEST_SIZE
        rows = _build_series(n, regime="risk_on")
        result = walk_forward_grid_search(rows, n_folds=3)
        # momentum genuinely predicts return → OOS ρ should be strongly positive.
        self.assertGreater(result["regimes"]["risk_on"]["oos_spearman_mean"], 0.5)

    def test_sorts_by_signal_date_not_insertion_order(self) -> None:
        n = WALKFORWARD_MIN_TRAIN_SIZE + 5 * WALKFORWARD_MIN_TEST_SIZE
        rows = _build_series(n, regime="risk_on")
        # Shuffle order; walk-forward must still respect chronological train→test.
        shuffled = rows[::-1]
        result_shuffled = walk_forward_grid_search(shuffled, n_folds=3)
        result_sorted = walk_forward_grid_search(rows, n_folds=3)
        self.assertEqual(
            result_shuffled["regimes"]["risk_on"]["sample_size"],
            result_sorted["regimes"]["risk_on"]["sample_size"],
        )
        self.assertEqual(
            result_shuffled["regimes"]["risk_on"]["oos_spearman_mean"],
            result_sorted["regimes"]["risk_on"]["oos_spearman_mean"],
        )

    def test_overfit_gap_present_when_folds_ok(self) -> None:
        n = WALKFORWARD_MIN_TRAIN_SIZE + 5 * WALKFORWARD_MIN_TEST_SIZE
        rows = _build_series(n, regime="risk_on")
        result = walk_forward_grid_search(rows, n_folds=3)
        regime_report = result["regimes"]["risk_on"]
        self.assertIn("overfit_gap", regime_report)
        # IS ρ should be ≥ mean OOS ρ for a signal-driven series (not strict
        # but the gap is a meaningful diagnostic).
        self.assertIsNotNone(regime_report["in_sample_spearman"])


class BuildTuningPayloadWalkForwardTests(unittest.TestCase):
    def test_walk_forward_included_by_default(self) -> None:
        rows = _build_series(5, regime="risk_on")
        payload = build_tuning_payload(rows)
        self.assertIn("walk_forward", payload)

    def test_walk_forward_can_be_skipped(self) -> None:
        rows = _build_series(5, regime="risk_on")
        payload = build_tuning_payload(rows, include_walk_forward=False)
        self.assertNotIn("walk_forward", payload)


if __name__ == "__main__":
    unittest.main()
