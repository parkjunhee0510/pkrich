from __future__ import annotations

import unittest
from datetime import date

from src.decision.action_change_reason import build_action_change_reasons
from src.types import MarketRegime, TickerDecision


class ActionChangeReasonTests(unittest.TestCase):
    def test_detects_upgrade_and_buy_threshold_crossing(self) -> None:
        rows = [
            {
                "signal_date": "2026-04-30",
                "ticker": "AAPL",
                "action": "watch",
                "conviction": "58",
                "regime": "neutral",
                "confidence_meta_json": '{"data_quality_score": 0.55}',
                "factors_json": '{"momentum": 0.2}',
            }
        ]
        decisions = [
            TickerDecision(
                ticker="AAPL",
                action="buy",
                conviction=68,
                factors={"momentum": 1.4},
                confidence_meta={"data_quality_score": 0.82},
            )
        ]

        result = build_action_change_reasons(
            decisions,
            rows,
            run_date=date(2026, 5, 1),
            market_regime=MarketRegime(regime="risk_on"),
        )

        self.assertEqual(result[0]["ticker"], "AAPL")
        self.assertEqual(result[0]["previous_action"], "watch")
        self.assertEqual(result[0]["current_action"], "buy")
        self.assertIn("action_upgraded", result[0]["reason_codes"])
        self.assertIn("conviction_crossed_buy_threshold", result[0]["reason_codes"])
        self.assertIn("macro_regime_changed", result[0]["reason_codes"])
        self.assertIn("data_quality_improved", result[0]["reason_codes"])

    def test_detects_calibrated_avoid_threshold_crossing(self) -> None:
        rows = [
            {
                "signal_date": "2026-04-30",
                "ticker": "AVAV",
                "action": "watch",
                "conviction": "58",
                "regime": "risk_on",
                "confidence_meta_json": "{}",
                "factors_json": "{}",
            }
        ]
        decisions = [
            TickerDecision(
                ticker="AVAV",
                action="avoid",
                conviction=55,
                factors={},
            )
        ]

        result = build_action_change_reasons(
            decisions,
            rows,
            run_date=date(2026, 5, 1),
            market_regime=MarketRegime(regime="risk_on"),
        )

        self.assertIn("action_downgraded", result[0]["reason_codes"])
        self.assertIn("conviction_crossed_avoid_threshold", result[0]["reason_codes"])

    def test_new_ticker_is_reported_without_previous_snapshot(self) -> None:
        result = build_action_change_reasons(
            [TickerDecision(ticker="MSFT", action="watch", conviction=50)],
            [],
            run_date=date(2026, 5, 1),
            market_regime=MarketRegime(regime="neutral"),
        )

        self.assertEqual(result[0]["ticker"], "MSFT")
        self.assertEqual(result[0]["reason_codes"], ["new_ticker", "insufficient_previous_snapshot"])


if __name__ == "__main__":
    unittest.main()
