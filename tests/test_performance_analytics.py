from __future__ import annotations

import unittest

from src.utils.performance_analytics import (
    build_conviction_calibration,
    build_factor_attribution,
    build_regime_performance,
    build_signal_performance,
)


ROWS = [
    {
        "signal_date": "2026-04-01",
        "ticker": "AAPL",
        "action": "buy",
        "conviction": "72",
        "regime": "risk_on",
        "return_1d": "+1.00%",
        "return_5d": "+4.00%",
        "return_20d": "N/A",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "False",
        "barrier_label": "take_profit",
        "factors_json": '{"momentum": 1.5, "valuation": -0.2}',
    },
    {
        "signal_date": "2026-04-01",
        "ticker": "MSFT",
        "action": "avoid",
        "conviction": "28",
        "regime": "risk_off",
        "return_1d": "-0.50%",
        "return_5d": "-3.00%",
        "return_20d": "N/A",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "False",
        "barrier_label": "stop_loss",
        "factors_json": '{"momentum": -1.0}',
    },
    {
        "signal_date": "2026-04-01",
        "ticker": "KO",
        "action": "watch",
        "conviction": "51",
        "regime": "neutral",
        "return_1d": "+0.00%",
        "return_5d": "+0.20%",
        "return_20d": "N/A",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "False",
        "barrier_label": "timeout",
        "factors_json": "{}",
    },
]


class PerformanceAnalyticsTests(unittest.TestCase):
    def test_signal_performance_groups_actions_and_watch_distribution(self) -> None:
        payload = build_signal_performance(ROWS)

        self.assertEqual(payload["buy"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["buy"]["5d"]["win_rate"], 1.0)
        self.assertEqual(payload["avoid"]["5d"]["win_rate"], 1.0)
        self.assertEqual(payload["watch"]["5d"]["directional_win_rate"], None)
        self.assertEqual(payload["watch"]["5d"]["return_distribution"]["positive"], 1)

    def test_signal_performance_skips_none_barrier_labels(self) -> None:
        rows = [
            {
                "action": "buy",
                "return_5d": "+2.00%",
                "evaluated_5d": "True",
                "barrier_label": None,
            }
        ]

        payload = build_signal_performance(rows)

        self.assertEqual(payload["buy"]["5d"]["completed_count"], 1)
        self.assertEqual(payload["buy"]["5d"]["triple_barrier_outcomes"], {})

    def test_signal_performance_treats_corrupt_returns_as_missing(self) -> None:
        rows = [
            {
                "action": "buy",
                "return_5d": "bad 2",
                "evaluated_5d": "True",
                "barrier_label": "take_profit",
            }
        ]

        payload = build_signal_performance(rows)

        self.assertEqual(payload["buy"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["buy"]["5d"]["completed_count"], 0)
        self.assertEqual(payload["buy"]["5d"]["missing_count"], 1)
        self.assertEqual(payload["buy"]["5d"]["triple_barrier_outcomes"], {})

    def test_conviction_calibration_uses_stable_buckets(self) -> None:
        payload = build_conviction_calibration(ROWS)

        self.assertEqual(payload["status"], "observational")
        self.assertEqual(payload["buckets"]["65_80"]["sample_count"], 1)
        self.assertEqual(payload["buckets"]["0_35"]["action_counts"]["avoid"], 1)

    def test_regime_performance_groups_by_regime_and_action(self) -> None:
        payload = build_regime_performance(ROWS)

        self.assertEqual(payload["risk_on"]["buy"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["risk_off"]["avoid"]["5d"]["avg_return"], -3.0)

    def test_regime_performance_groups_null_and_blank_regimes_as_unknown(self) -> None:
        rows = [
            {"action": "buy", "regime": None},
            {"action": "watch", "regime": ""},
            {"action": "avoid", "regime": "  "},
            {"action": "buy", "regime": "risk_on"},
        ]

        payload = build_regime_performance(rows)

        self.assertNotIn("none", payload)
        self.assertEqual(payload["unknown"]["buy"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["unknown"]["watch"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["unknown"]["avoid"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["risk_on"]["buy"]["5d"]["sample_count"], 1)

    def test_factor_attribution_skips_missing_factors(self) -> None:
        payload = build_factor_attribution(ROWS)

        self.assertEqual(payload["factors"]["momentum"]["sample_count"], 2)
        self.assertEqual(payload["missing_factor_sample_count"], 1)


if __name__ == "__main__":
    unittest.main()
