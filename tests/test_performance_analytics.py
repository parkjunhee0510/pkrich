from __future__ import annotations

import unittest

from src.utils.performance_analytics import (
    build_ai_recommendation_backtest,
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
        "barrier_label": "hit",
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
        "barrier_label": "stop",
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

AI_BACKTEST_ROWS = [
    {
        "signal_date": "2026-04-02",
        "ticker": "AAPL",
        "action": "buy",
        "conviction": "82",
        "regime": "risk_on",
        "catalyst_tag": "earnings",
        "return_1d": "+1.00%",
        "return_5d": "+3.00%",
        "return_20d": "+8.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
    {
        "signal_date": "2026-04-02",
        "ticker": "MSFT",
        "action": "avoid",
        "conviction": "88",
        "regime": "risk_off",
        "catalyst_tag": "guidance",
        "return_1d": "-0.50%",
        "return_5d": "-2.00%",
        "return_20d": "-5.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
    {
        "signal_date": "2026-04-02",
        "ticker": "KO",
        "action": "watch",
        "conviction": "70",
        "regime": "neutral",
        "catalyst_tag": "defensive",
        "return_1d": "+0.20%",
        "return_5d": "+0.40%",
        "return_20d": "N/A",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "False",
    },
    {
        "signal_date": "2026-04-02",
        "ticker": "AMD",
        "action": "buy",
        "conviction": "55",
        "regime": "risk_on",
        "catalyst_tag": "product",
        "return_1d": "-1.00%",
        "return_5d": "-3.00%",
        "return_20d": "-6.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
    {
        "signal_date": "2026-04-02",
        "ticker": "BRK",
        "action": "watch",
        "conviction": "66",
        "regime": "neutral",
        "catalyst_tag": "quality",
        "return_1d": "+2.00%",
        "return_5d": "+40.00%",
        "return_20d": "+120.00%",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "True",
    },
    {
        "signal_date": "2026-04-02",
        "ticker": "NVDA",
        "action": "buy",
        "conviction": "78",
        "regime": "risk_on",
        "catalyst_tag": "ai",
        "return_1d": "+4.00%",
        "return_5d": "+50.00%",
        "return_20d": "N/A",
        "evaluated_1d": "True",
        "evaluated_5d": "True",
        "evaluated_20d": "False",
    },
]


class PerformanceAnalyticsTests(unittest.TestCase):
    def test_signal_performance_groups_actions_and_watch_distribution(self) -> None:
        payload = build_signal_performance(ROWS)

        self.assertEqual(payload["buy"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["buy"]["5d"]["win_rate"], 1.0)
        self.assertEqual(payload["avoid"]["5d"]["win_rate"], 1.0)
        self.assertIsNone(payload["watch"]["5d"]["directional_win_rate"])
        self.assertEqual(payload["watch"]["5d"]["return_distribution"]["positive"], 1)

    def test_conviction_calibration_uses_stable_buckets(self) -> None:
        payload = build_conviction_calibration(ROWS)

        self.assertEqual(payload["status"], "observational")
        self.assertEqual(payload["buckets"]["65_80"]["sample_count"], 1)
        self.assertEqual(payload["buckets"]["0_35"]["action_counts"]["avoid"], 1)

    def test_regime_performance_groups_by_regime_and_action(self) -> None:
        payload = build_regime_performance(ROWS)

        self.assertEqual(payload["risk_on"]["buy"]["5d"]["sample_count"], 1)
        self.assertEqual(payload["risk_off"]["avoid"]["5d"]["avg_return"], -3.0)

    def test_factor_attribution_skips_missing_factors(self) -> None:
        payload = build_factor_attribution(ROWS)

        self.assertEqual(payload["factors"]["momentum"]["sample_count"], 2)
        self.assertEqual(payload["missing_factor_sample_count"], 1)

    def test_ai_recommendation_backtest_scores_buy_avoid_and_watch(self) -> None:
        payload = build_ai_recommendation_backtest(AI_BACKTEST_ROWS)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["basis"], "final_action")
        self.assertEqual(payload["summary"]["sample_count"], 6)
        self.assertEqual(payload["summary"]["completed_20d_count"], 4)
        self.assertEqual(payload["by_action"]["buy"]["20d"]["sample_count"], 3)
        self.assertEqual(payload["by_action"]["buy"]["20d"]["completed_count"], 2)
        self.assertEqual(payload["by_action"]["buy"]["20d"]["win_rate"], 0.5)
        self.assertEqual(payload["by_action"]["avoid"]["20d"]["win_rate"], 1.0)
        self.assertIsNone(payload["by_action"]["watch"]["20d"]["win_rate"])
        self.assertEqual(payload["by_action"]["watch"]["20d"]["missing_count"], 1)

    def test_ai_recommendation_backtest_builds_conviction_and_examples(self) -> None:
        payload = build_ai_recommendation_backtest(AI_BACKTEST_ROWS)

        self.assertEqual(payload["conviction_buckets"]["65_80"]["sample_count"], 3)
        self.assertEqual(payload["conviction_buckets"]["80_100"]["sample_count"], 2)
        self.assertEqual(
            payload["conviction_buckets"]["80_100"]["action_counts"],
            {"avoid": 1, "buy": 1},
        )
        self.assertEqual(payload["summary"]["best_action"], "watch")
        self.assertEqual(payload["notable_examples"]["best"][0]["ticker"], "BRK")
        self.assertIsNone(
            next(
                example
                for example in payload["notable_examples"]["best"]
                if example["ticker"] == "NVDA"
            )["return_20d"]
        )
        self.assertEqual(payload["notable_examples"]["worst"][0]["ticker"], "AMD")
        self.assertEqual(payload["ticker_leaderboard"][0]["ticker"], "BRK")
        leaderboard = {
            row["ticker"]: (index, row)
            for index, row in enumerate(payload["ticker_leaderboard"])
        }
        self.assertEqual(leaderboard["BRK"][1]["watch_signals"], 1)
        self.assertEqual(leaderboard["BRK"][1]["completed_20d_count"], 1)
        self.assertEqual(leaderboard["MSFT"][1]["avg_return_20d"], -5.0)
        self.assertEqual(leaderboard["MSFT"][1]["win_rate_20d"], 1.0)
        self.assertEqual(leaderboard["NVDA"][1]["completed_20d_count"], 0)
        self.assertLess(leaderboard["BRK"][0], leaderboard["AAPL"][0])

    def test_ai_recommendation_backtest_empty_input_is_stable(self) -> None:
        payload = build_ai_recommendation_backtest([])

        self.assertEqual(payload["status"], "insufficient_data")
        self.assertEqual(payload["summary"]["sample_count"], 0)
        self.assertEqual(payload["by_action"], {})
        self.assertEqual(payload["ticker_leaderboard"], [])


if __name__ == "__main__":
    unittest.main()
