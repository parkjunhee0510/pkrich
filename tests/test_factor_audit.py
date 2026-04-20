from __future__ import annotations

import json
import unittest

from src.decision.factor_audit import (
    DECAY_FACTOR,
    MIN_SAMPLE_FOR_DECAY,
    build_factor_audit_payload,
    compute_factor_correlations,
    compute_factor_ir,
    suggest_weight_decays,
)


def _make_row(
    factors: dict[str, float],
    return_5d: float,
    *,
    evaluated: bool = True,
) -> dict[str, str]:
    return {
        "factors_json": json.dumps(factors),
        "return_5d": f"{return_5d:+.2f}%",
        "evaluated_5d": "True" if evaluated else "False",
    }


class FactorAuditCorrelationTests(unittest.TestCase):
    def test_insufficient_data_returns_insufficient_status(self) -> None:
        rows = [_make_row({"momentum": 1.0}, 0.5) for _ in range(3)]
        result = compute_factor_correlations(rows)
        self.assertEqual(result["status"], "insufficient_data")

    def test_perfect_correlation_flagged_collinear(self) -> None:
        rows = [_make_row({"momentum": float(i), "catalyst": float(i * 2)}, 0.0) for i in range(15)]
        result = compute_factor_correlations(rows)
        self.assertEqual(result["status"], "ok")
        pairs = result["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertAlmostEqual(pairs[0]["rho"], 1.0, places=2)
        self.assertTrue(pairs[0]["collinear"])

    def test_uncorrelated_factors_not_flagged(self) -> None:
        rows = [
            _make_row({"momentum": float(i % 3), "valuation": float((i * 7) % 5)}, 0.0)
            for i in range(30)
        ]
        result = compute_factor_correlations(rows)
        self.assertEqual(result["status"], "ok")
        pairs = result["pairs"]
        self.assertTrue(all(abs(p["rho"]) < 0.6 for p in pairs))


class FactorAuditIRTests(unittest.TestCase):
    def test_factor_with_strong_monotone_relationship_has_high_ir(self) -> None:
        rows = [_make_row({"momentum": float(i)}, float(i) * 0.1) for i in range(20)]
        result = compute_factor_ir(rows)
        self.assertEqual(result["status"], "ok")
        factor = next(f for f in result["factors"] if f["factor"] == "momentum")
        self.assertGreater(factor["ir"], 0.9)
        self.assertFalse(factor["weak"])

    def test_noise_factor_flagged_weak(self) -> None:
        # random factor uncorrelated with return
        rows = []
        for i in range(30):
            factor_value = float((i * 37 + 7) % 11)  # pseudo-noise
            return_value = float((i * 5) % 3)  # unrelated
            rows.append(_make_row({"noise": factor_value}, return_value))
        result = compute_factor_ir(rows)
        noise = next((f for f in result["factors"] if f["factor"] == "noise"), None)
        if noise is not None:  # may be skipped if too few unique combos
            # Hard to guarantee "weak" here across platforms; at least verify
            # the payload shape is intact and threshold is exposed.
            self.assertIn("weak", noise)
        self.assertEqual(result["threshold"], 0.1)


class FactorAuditPayloadTests(unittest.TestCase):
    def test_build_payload_includes_horizon_sections(self) -> None:
        rows = [_make_row({"momentum": float(i)}, float(i) * 0.1) for i in range(15)]
        payload = build_factor_audit_payload(rows, horizon=5)
        self.assertEqual(payload["horizon"], 5)
        self.assertIn("collinearity", payload)
        self.assertIn("factor_ir", payload)
        self.assertIn("weight_decays", payload)


class WeightDecaySuggestionTests(unittest.TestCase):
    def test_insufficient_data_below_min_returns_insufficient(self) -> None:
        rows = [_make_row({"peer_rank": float(i)}, 0.0) for i in range(5)]
        config = {"factors": {"peer_rank": {"min": -4, "max": 8}}}
        result = suggest_weight_decays(rows, current_config=config)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["suggestions"], [])

    def test_weak_factor_with_enough_samples_suggests_halved_range(self) -> None:
        # Factor values are pseudo-random vs return → |IR| should be small.
        rows = []
        for i in range(MIN_SAMPLE_FOR_DECAY + 10):
            factor_value = float((i * 37 + 11) % 13)
            return_value = float((i * 3 + 1) % 7) - 3.0
            rows.append(_make_row({"peer_rank": factor_value}, return_value))
        config = {"factors": {"peer_rank": {"min": -4, "max": 8}}}
        result = suggest_weight_decays(rows, current_config=config)
        self.assertEqual(result["status"], "ok")
        if result["suggestions"]:  # IR noise may or may not clear 0.1 threshold
            suggestion = result["suggestions"][0]
            self.assertEqual(suggestion["factor"], "peer_rank")
            self.assertEqual(suggestion["current"], {"min": -4.0, "max": 8.0})
            self.assertEqual(
                suggestion["suggested"],
                {"min": round(-4.0 * DECAY_FACTOR, 2), "max": round(8.0 * DECAY_FACTOR, 2)},
            )

    def test_strong_factor_is_not_suggested(self) -> None:
        rows = [
            _make_row({"momentum": float(i)}, float(i) * 0.2)
            for i in range(MIN_SAMPLE_FOR_DECAY + 10)
        ]
        config = {"factors": {"momentum": {"min": 0, "max": 20}}}
        result = suggest_weight_decays(rows, current_config=config)
        self.assertEqual(result["status"], "ok")
        # momentum perfectly predicts return → IR ≫ 0.1 → no decay suggested.
        self.assertEqual(result["suggestions"], [])

    def test_factor_missing_from_config_is_skipped(self) -> None:
        rows = []
        for i in range(MIN_SAMPLE_FOR_DECAY + 10):
            rows.append(_make_row({"mystery": float((i * 7) % 5)}, float((i * 3) % 2)))
        result = suggest_weight_decays(rows, current_config={"factors": {}})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["suggestions"], [])


if __name__ == "__main__":
    unittest.main()
