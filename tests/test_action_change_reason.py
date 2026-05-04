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

    def test_new_ticker_is_reported_without_previous_snapshot(self) -> None:
        result = build_action_change_reasons(
            [TickerDecision(ticker="MSFT", action="watch", conviction=50)],
            [],
            run_date=date(2026, 5, 1),
            market_regime=MarketRegime(regime="neutral"),
        )

        self.assertEqual(result[0]["ticker"], "MSFT")
        self.assertEqual(result[0]["reason_codes"], ["new_ticker", "insufficient_previous_snapshot"])

    def test_missing_previous_action_is_insufficient_snapshot_without_action_movement(self) -> None:
        result = build_action_change_reasons(
            [TickerDecision(ticker="AAPL", action="buy", conviction=70)],
            [
                {
                    "signal_date": "2026-04-30",
                    "ticker": "AAPL",
                    "conviction": "",
                    "confidence_meta_json": "{}",
                    "factors_json": "{}",
                }
            ],
            run_date=date(2026, 5, 1),
            market_regime=MarketRegime(regime="neutral"),
        )

        reason_codes = result[0]["reason_codes"]
        self.assertIn("insufficient_previous_snapshot", reason_codes)
        self.assertNotIn("action_unchanged", reason_codes)
        self.assertNotIn("action_upgraded", reason_codes)
        self.assertNotIn("action_downgraded", reason_codes)

    def test_avoid_threshold_boundary_uses_strict_below_threshold(self) -> None:
        cases = [
            (35, 34, "conviction_crossed_avoid_threshold", True),
            (36, 35, "conviction_crossed_avoid_threshold", False),
            (34, 35, "conviction_recovered_from_avoid_threshold", True),
            (35, 36, "conviction_recovered_from_avoid_threshold", False),
        ]

        for previous_conviction, current_conviction, code, expected in cases:
            with self.subTest(
                previous_conviction=previous_conviction,
                current_conviction=current_conviction,
                code=code,
            ):
                result = build_action_change_reasons(
                    [
                        TickerDecision(
                            ticker="AMD",
                            action="watch",
                            conviction=current_conviction,
                            confidence_meta={"data_quality_score": 0.7},
                        )
                    ],
                    [
                        {
                            "signal_date": "2026-04-30",
                            "ticker": "AMD",
                            "action": "watch",
                            "conviction": str(previous_conviction),
                            "regime": "neutral",
                            "confidence_meta_json": '{"data_quality_score": 0.7}',
                            "factors_json": "{}",
                        }
                    ],
                    run_date=date(2026, 5, 1),
                    market_regime=MarketRegime(regime="neutral"),
                )

                if expected:
                    self.assertIn(code, result[0]["reason_codes"])
                else:
                    self.assertNotIn(code, result[0]["reason_codes"])

    def test_non_finite_numeric_values_are_treated_as_missing(self) -> None:
        result = build_action_change_reasons(
            [
                TickerDecision(
                    ticker="NVDA",
                    action="watch",
                    conviction=50,
                    factors={"momentum": 1.0},
                    confidence_meta={"data_quality_score": 0.7},
                )
            ],
            [
                {
                    "signal_date": "2026-04-30",
                    "ticker": "NVDA",
                    "action": "watch",
                    "conviction": "NaN",
                    "regime": "neutral",
                    "confidence_meta_json": '{"data_quality_score": Infinity}',
                    "factors_json": '{"momentum": NaN}',
                }
            ],
            run_date=date(2026, 5, 1),
            market_regime=MarketRegime(regime="neutral"),
        )

        self.assertIsNone(result[0]["previous_conviction"])
        self.assertIsNone(result[0]["previous_data_quality_score"])
        self.assertIn("insufficient_previous_snapshot", result[0]["reason_codes"])
        momentum = next(item for item in result[0]["contributors"] if item["factor"] == "momentum")
        self.assertIsNone(momentum["previous_value"])

    def test_risk_off_uses_higher_buy_threshold(self) -> None:
        cases = [
            (70, 74, "conviction_crossed_buy_threshold", False),
            (70, 76, "conviction_crossed_buy_threshold", True),
            (76, 74, "conviction_fell_below_buy_threshold", True),
        ]

        for previous_conviction, current_conviction, code, expected in cases:
            with self.subTest(
                previous_conviction=previous_conviction,
                current_conviction=current_conviction,
                code=code,
            ):
                result = build_action_change_reasons(
                    [
                        TickerDecision(
                            ticker="TSLA",
                            action="watch",
                            conviction=current_conviction,
                            confidence_meta={"data_quality_score": 0.7},
                        )
                    ],
                    [
                        {
                            "signal_date": "2026-04-30",
                            "ticker": "TSLA",
                            "action": "watch",
                            "conviction": str(previous_conviction),
                            "regime": "risk_off",
                            "confidence_meta_json": '{"data_quality_score": 0.7}',
                            "factors_json": "{}",
                        }
                    ],
                    run_date=date(2026, 5, 1),
                    market_regime=MarketRegime(regime="risk_off"),
                )

                if expected:
                    self.assertIn(code, result[0]["reason_codes"])
                else:
                    self.assertNotIn(code, result[0]["reason_codes"])


if __name__ == "__main__":
    unittest.main()
