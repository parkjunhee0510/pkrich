from __future__ import annotations

import unittest

from src.eval.config import (
    DEFAULT_THRESHOLDS,
    DEFAULT_REPLAY_TICKERS,
    DEFAULT_RUNS_PER_TICKER,
    DEFAULT_WINDOW_DAYS,
    DEFAULT_MAX_REPLAY_COST_USD,
    severity_for,
)


class TestThresholds(unittest.TestCase):
    def test_all_checks_have_thresholds(self):
        expected = {
            "I1", "I2", "I3", "I4",
            "O1", "O2", "O3", "O4", "O5",
            "D1", "D2", "D3",
            "R1", "R2", "R3",
        }
        self.assertEqual(set(DEFAULT_THRESHOLDS.keys()), expected)

    def test_defaults(self):
        self.assertEqual(DEFAULT_WINDOW_DAYS, 14)
        self.assertEqual(DEFAULT_RUNS_PER_TICKER, 3)
        self.assertEqual(DEFAULT_MAX_REPLAY_COST_USD, 1.0)
        self.assertEqual(len(DEFAULT_REPLAY_TICKERS), 5)

    def test_severity_for_pass_warn_fail(self):
        # I3 thresholds: pass when format_count <= 1, warn when 2, fail when >= 3
        self.assertEqual(severity_for("I3", value=1, kind="format_count"), "pass")
        self.assertEqual(severity_for("I3", value=2, kind="format_count"), "warn")
        self.assertEqual(severity_for("I3", value=3, kind="format_count"), "fail")


if __name__ == "__main__":
    unittest.main()
