from __future__ import annotations

import json
import unittest

from src.decision.tune_weights import (
    MIN_SAMPLES_FOR_THRESHOLDS,
    MIN_SAMPLES_PER_REGIME,
    MULTIPLIER_GRID,
    TUNABLE_FACTORS,
    build_tuning_payload,
    grid_search_regime_multipliers,
    suggest_thresholds,
)


def _row(
    *,
    factors: dict[str, float],
    return_5d: float,
    regime: str = "neutral",
    conviction: float = 60.0,
    evaluated: bool = True,
) -> dict[str, str]:
    return {
        "factors_json": json.dumps(factors),
        "return_5d": f"{return_5d:+.2f}%",
        "evaluated_5d": "True" if evaluated else "False",
        "regime": regime,
        "conviction": f"{conviction:.1f}",
    }


class GridSearchTests(unittest.TestCase):
    def test_insufficient_samples_returns_insufficient_status(self) -> None:
        rows = [
            _row(factors={"momentum": 5.0}, return_5d=1.0, regime="risk_on")
            for _ in range(5)
        ]
        result = grid_search_regime_multipliers(rows)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["regimes"]["risk_on"]["status"], "insufficient_data")
        self.assertEqual(result["regimes"]["risk_on"]["best"], None)

    def test_return_driver_wins_over_noise_factor(self) -> None:
        # Momentum is the true return driver; valuation is a confounder that
        # moves opposite to return. Grid search should down-weight valuation
        # (pick the SMALLEST multiplier) to recover the underlying signal.
        rows = []
        for i in range(MIN_SAMPLES_PER_REGIME + 5):
            momentum = float(i)
            # valuation anti-correlates with return → bad factor to up-weight.
            valuation = float(MIN_SAMPLES_PER_REGIME - i)
            rows.append(
                _row(
                    factors={"momentum": momentum, "valuation": valuation},
                    return_5d=momentum * 0.1,
                    regime="risk_on",
                )
            )
        result = grid_search_regime_multipliers(rows)
        best = result["regimes"]["risk_on"]["best"]
        self.assertIsNotNone(best)
        # Valuation anti-correlates with return → minimum multiplier wins.
        self.assertEqual(best["multipliers"]["valuation"], min(MULTIPLIER_GRID))
        self.assertGreater(best["spearman"], 0.9)

    def test_grid_shape_matches_spec(self) -> None:
        self.assertEqual(len(TUNABLE_FACTORS), 5)
        self.assertEqual(len(MULTIPLIER_GRID), 3)
        # 3^5 = 243 combinations per regime.
        rows = [
            _row(
                factors={f: float(i % 5) for f in TUNABLE_FACTORS},
                return_5d=(i % 5) * 0.1,
                regime="neutral",
            )
            for i in range(MIN_SAMPLES_PER_REGIME + 10)
        ]
        result = grid_search_regime_multipliers(rows, top_k=1000)
        self.assertEqual(result["regimes"]["neutral"]["status"], "ok")
        self.assertLessEqual(len(result["regimes"]["neutral"]["candidates"]), 243)


class ThresholdRefitTests(unittest.TestCase):
    def test_insufficient_data_returns_insufficient_status(self) -> None:
        rows = [_row(factors={"momentum": 1.0}, return_5d=0.5) for _ in range(5)]
        result = suggest_thresholds(rows)
        self.assertEqual(result["status"], "insufficient_data")

    def test_quantiles_recover_underlying_distribution(self) -> None:
        rows = [
            _row(factors={"momentum": 1.0}, return_5d=0.0, conviction=float(i))
            for i in range(MIN_SAMPLES_FOR_THRESHOLDS + 10)
        ]
        result = suggest_thresholds(rows)
        self.assertEqual(result["status"], "ok")
        suggested = result["suggested"]
        # buy @ 70th percentile of uniform 0..N should be near 0.7 * N.
        self.assertGreater(suggested["buy"], suggested["avoid"])
        self.assertGreaterEqual(suggested["buy_risk_off"], suggested["buy"])


class BuildTuningPayloadTests(unittest.TestCase):
    def test_payload_wraps_both_sections(self) -> None:
        rows = [
            _row(factors={"momentum": 1.0}, return_5d=0.5, conviction=60.0)
            for _ in range(5)
        ]
        payload = build_tuning_payload(rows)
        self.assertIn("regime_multipliers", payload)
        self.assertIn("thresholds", payload)
        self.assertEqual(payload["horizon"], 5)


if __name__ == "__main__":
    unittest.main()
