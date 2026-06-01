from __future__ import annotations

import unittest

from src.output.schema import SCHEMA_VERSION
from src.utils.strategy_simulator import build_strategy_simulator


def signal(
    ticker: str,
    signal_date: str,
    final_action: str,
    conviction: float | None = None,
    signal_direction: str | None = "bull",
    llm_direction: str | None = "bull",
) -> dict:
    return {
        "ticker": ticker,
        "signal_date": signal_date,
        "final_action": final_action,
        "conviction": conviction,
        "signal_direction": signal_direction,
        "llm_direction": llm_direction,
    }


def price(
    ticker: str,
    date: str,
    open_price: float | None,
    high: float,
    low: float,
    close: float,
) -> dict:
    return {
        "ticker": ticker,
        "date": date,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
    }


class StrategySimulatorTests(unittest.TestCase):
    def test_empty_inputs_return_insufficient_data(self) -> None:
        payload = build_strategy_simulator([], [])

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["status"], "insufficient_data")
        self.assertEqual(payload["as_of"], "")
        self.assertEqual(payload["mode"], "observational_long_only")
        self.assertEqual(payload["basis"], "final_action")
        self.assertEqual(
            payload["inputs"],
            {"signal_count": 0, "usable_signal_count": 0, "price_row_count": 0},
        )
        self.assertEqual(
            payload["assumptions"],
            {
                "initial_capital": 100000.0,
                "entry_timing": "next_trading_day_open",
                "avoid_exit_timing": "next_trading_day_open",
                "short_selling": False,
                "leverage": False,
                "fee_rate": 0.001,
                "slippage_rate": 0.0005,
            },
        )
        self.assertEqual(payload["presets"], {})
        self.assertIsInstance(payload["notes"], list)
        self.assertIn("No usable signal or price rows", payload["notes"][0])

    def test_ok_root_payload_contains_required_fields(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "watch"),
                signal("", "2026-01-01", "buy"),
            ],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 101, 102, 100, 101),
            ],
        )

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["as_of"], "2026-01-03")
        self.assertEqual(payload["mode"], "observational_long_only")
        self.assertEqual(payload["basis"], "final_action")
        self.assertEqual(
            payload["inputs"],
            {"signal_count": 2, "usable_signal_count": 1, "price_row_count": 2},
        )
        self.assertEqual(payload["assumptions"]["initial_capital"], 100000.0)
        self.assertEqual(payload["assumptions"]["entry_timing"], "next_trading_day_open")
        self.assertEqual(payload["assumptions"]["avoid_exit_timing"], "next_trading_day_open")
        self.assertFalse(payload["assumptions"]["short_selling"])
        self.assertFalse(payload["assumptions"]["leverage"])
        self.assertEqual(payload["assumptions"]["fee_rate"], 0.001)
        self.assertEqual(payload["assumptions"]["slippage_rate"], 0.0005)
        self.assertIsInstance(payload["notes"], list)

    def test_ok_payload_contains_three_korean_labels(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "watch")],
            [price("AAA", "2026-01-02", 100, 101, 99, 100)],
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            [payload["presets"][key]["label"] for key in ("conservative", "balanced", "aggressive")],
            ["보수형", "균형형", "공격형"],
        )

    def test_preset_params_and_summary_include_required_capital_fields(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "watch")],
            [price("AAA", "2026-01-02", 100, 101, 99, 100)],
        )

        for preset in payload["presets"].values():
            self.assertEqual(
                set(preset["params"]),
                {
                    "initial_capital",
                    "position_size_pct",
                    "max_positions",
                    "stop_loss_pct",
                    "take_profit_pct",
                    "fee_rate",
                    "slippage_rate",
                },
            )
            self.assertEqual(preset["params"]["initial_capital"], 100000.0)
            self.assertEqual(preset["params"]["fee_rate"], 0.001)
            self.assertEqual(preset["params"]["slippage_rate"], 0.0005)
            self.assertEqual(preset["summary"]["initial_capital"], 100000.0)

    def test_entry_candidates_show_latest_buy_priority_and_pending_next_open(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "watch", conviction=50),
                signal("AAA", "2026-01-03", "buy", conviction=70, signal_direction="bull", llm_direction="bear"),
                signal("BBB", "2026-01-03", "buy", conviction=90, signal_direction="bull", llm_direction="bull"),
                signal("CCC", "2026-01-03", "watch", conviction=100),
            ],
            [
                price("AAA", "2026-01-03", 105, 106, 104, 105),
                price("BBB", "2026-01-03", 50, 51, 49, 50),
                price("CCC", "2026-01-03", 70, 71, 69, 70),
            ],
        )

        candidates = payload["presets"]["balanced"]["entry_candidates"]

        self.assertEqual([candidate["ticker"] for candidate in candidates], ["BBB", "AAA"])
        self.assertEqual(
            set(candidates[0]),
            {
                "rank",
                "ticker",
                "status",
                "status_label",
                "signal_date",
                "conviction",
                "entry_date",
                "entry_price",
                "stop_price",
                "take_profit_price",
                "position_size_pct",
                "target_notional",
                "required_cash",
                "available_cash",
                "llm_alignment",
                "signal_direction",
                "llm_direction",
                "reason",
            },
        )
        self.assertEqual(candidates[0]["rank"], 1)
        self.assertEqual(candidates[0]["status"], "pending_next_open")
        self.assertEqual(candidates[0]["status_label"], "다음 open 대기")
        self.assertEqual(candidates[0]["signal_date"], "2026-01-03")
        self.assertEqual(candidates[0]["conviction"], 90.0)
        self.assertIsNone(candidates[0]["entry_date"])
        self.assertIsNone(candidates[0]["entry_price"])
        self.assertIsNone(candidates[0]["stop_price"])
        self.assertIsNone(candidates[0]["take_profit_price"])
        self.assertEqual(candidates[0]["llm_alignment"], "aligned")
        self.assertEqual(candidates[1]["llm_alignment"], "conflict")

    def test_entry_candidates_mark_already_held_with_risk_levels(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 101, 102, 100, 101),
            ],
        )

        candidate = payload["presets"]["balanced"]["entry_candidates"][0]

        self.assertEqual(candidate["ticker"], "AAA")
        self.assertEqual(candidate["status"], "already_held")
        self.assertEqual(candidate["status_label"], "이미 보유")
        self.assertEqual(candidate["entry_date"], "2026-01-02")
        self.assertEqual(candidate["entry_price"], 100.0)
        self.assertEqual(candidate["stop_price"], 92.0)
        self.assertEqual(candidate["take_profit_price"], 118.0)
        self.assertEqual(candidate["position_size_pct"], 0.1)
        self.assertAlmostEqual(candidate["target_notional"], 10000.0)
        self.assertIsNone(candidate["required_cash"])
        self.assertAlmostEqual(candidate["available_cash"], 89985.0)
        self.assertEqual(candidate["reason"], "현재 보유 중")

    def test_buy_enters_next_trading_day_open_and_deducts_entry_cost(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [price("AAA", "2026-01-02", 110, 112, 109, 111)],
        )

        balanced = payload["presets"]["balanced"]
        position = balanced["open_positions"][0]

        self.assertEqual(position["ticker"], "AAA")
        self.assertEqual(position["entry_date"], "2026-01-02")
        self.assertEqual(position["entry_price"], 110.0)
        self.assertAlmostEqual(position["notional"], 10000.0)
        self.assertAlmostEqual(balanced["summary"]["cash"], 89985.0)
        self.assertAlmostEqual(position["unrealized_pnl"], 75.9090909091)
        self.assertAlmostEqual(position["return_pct"], 0.7590909091)

    def test_same_day_entries_recompute_position_size_after_entry_costs(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=90),
                signal("BBB", "2026-01-01", "buy", conviction=80),
            ],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("BBB", "2026-01-02", 100, 101, 99, 100),
            ],
        )

        positions = payload["presets"]["balanced"]["open_positions"]

        self.assertAlmostEqual(positions[0]["notional"], 10000.0)
        self.assertAlmostEqual(positions[1]["notional"], 9998.5)

    def test_conviction_priority_and_max_position_skip(self) -> None:
        signals = [
            signal("AAA", "2026-01-01", "buy", conviction=10),
            signal("BBB", "2026-01-01", "buy", conviction=99),
            signal("CCC", "2026-01-01", "buy", conviction=50),
            signal("DDD", "2026-01-01", "buy", conviction=20),
            signal("EEE", "2026-01-01", "buy", conviction=30),
            signal("FFF", "2026-01-01", "buy", conviction=None),
            signal("GGG", "2026-01-01", "buy", conviction=75),
        ]
        prices = [
            price(ticker, "2026-01-02", 100, 101, 99, 100)
            for ticker in ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]
        ]

        payload = build_strategy_simulator(signals, prices)
        conservative = payload["presets"]["conservative"]

        self.assertEqual(
            [position["ticker"] for position in conservative["open_positions"]],
            ["BBB", "GGG", "CCC", "EEE", "DDD", "AAA"],
        )
        self.assertEqual(conservative["skipped_entries"]["by_reason"]["max_positions_reached"], 1)
        self.assertEqual(conservative["skipped_entries"]["examples"][0]["ticker"], "FFF")
        self.assertEqual(conservative["skipped_entries"]["examples"][0]["reason"], "max_positions_reached")

    def test_missing_next_open_skips_entry(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [price("AAA", "2026-01-02", None, 101, 99, 100)],
        )

        balanced = payload["presets"]["balanced"]
        self.assertEqual(balanced["summary"]["open_position_count"], 0)
        self.assertEqual(balanced["skipped_entries"]["by_reason"]["missing_entry_price"], 1)

    def test_stop_loss_exits_when_daily_low_reaches_threshold(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 99, 100, 91, 92),
            ],
        )

        trade = payload["presets"]["balanced"]["trades"][0]

        self.assertEqual(trade["exit_date"], "2026-01-03")
        self.assertEqual(trade["exit_reason"], "stop_loss")
        self.assertAlmostEqual(trade["exit_price"], 92.0)
        self.assertAlmostEqual(trade["return_pct"], -8.288)

    def test_take_profit_exits_when_high_reaches_threshold(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 100, 118, 99, 117),
            ],
        )

        trade = payload["presets"]["balanced"]["trades"][0]

        self.assertEqual(trade["exit_reason"], "take_profit")
        self.assertAlmostEqual(trade["exit_price"], 118.0)
        self.assertAlmostEqual(trade["return_pct"], 17.673)

    def test_same_day_stop_take_uses_stop_first(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [
                price("AAA", "2026-01-02", 100, 120, 90, 110),
            ],
        )

        trade = payload["presets"]["balanced"]["trades"][0]

        self.assertEqual(trade["exit_reason"], "stop_loss")
        self.assertAlmostEqual(trade["exit_price"], 92.0)

    def test_repeated_buy_while_already_held_is_skipped(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=80),
                signal("AAA", "2026-01-02", "buy", conviction=90),
            ],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 101, 102, 100, 101),
            ],
        )

        skipped = payload["presets"]["balanced"]["skipped_entries"]
        self.assertEqual(skipped["by_reason"]["already_held"], 1)
        self.assertEqual(skipped["examples"][0]["ticker"], "AAA")
        self.assertEqual(skipped["examples"][0]["reason"], "already_held")

    def test_insufficient_cash_skip_is_tracked(self) -> None:
        signals = [
            signal(f"T{i:02d}", "2026-01-01", "buy", conviction=100 - i)
            for i in range(11)
        ]
        prices = [
            price(f"T{i:02d}", "2026-01-02", 100, 101, 99, 100)
            for i in range(11)
        ]

        payload = build_strategy_simulator(signals, prices)
        aggressive = payload["presets"]["aggressive"]

        self.assertEqual(aggressive["summary"]["open_position_count"], 6)
        self.assertEqual(aggressive["skipped_entries"]["by_reason"]["insufficient_cash"], 5)

    def test_sell_side_fee_slippage_reduces_realized_pnl_and_cash(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=80),
                signal("AAA", "2026-01-02", "avoid", conviction=20),
            ],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 100, 101, 99, 100),
            ],
        )

        balanced = payload["presets"]["balanced"]
        trade = balanced["trades"][0]

        self.assertAlmostEqual(trade["entry_cost"], 15.0)
        self.assertAlmostEqual(trade["exit_cost"], 15.0)
        self.assertAlmostEqual(trade["realized_pnl"], -30.0)
        self.assertAlmostEqual(balanced["summary"]["cash"], 99970.0)

    def test_empty_closed_trade_metrics_are_null_not_zero(self) -> None:
        payload = build_strategy_simulator(
            [signal("AAA", "2026-01-01", "buy", conviction=80)],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-03", 100, 101, 99, 100),
            ],
        )

        summary = payload["presets"]["balanced"]["summary"]
        diagnostics = payload["presets"]["balanced"]["llm_direction_diagnostics"]

        self.assertIsNone(summary["win_rate"])
        self.assertIsNone(summary["avg_closed_trade_return_pct"])
        self.assertIsNone(diagnostics["conflict"]["avg_trade_return_pct"])
        self.assertIsNone(diagnostics["conflict"]["win_rate"])

    def test_trade_and_open_position_include_required_fields(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=80),
                signal("BBB", "2026-01-01", "buy", conviction=70),
            ],
            [
                price("AAA", "2026-01-02", 100, 118, 99, 118),
                price("BBB", "2026-01-02", 100, 101, 99, 100),
                price("BBB", "2026-01-03", 100, 101, 99, 110),
            ],
        )

        trade = payload["presets"]["balanced"]["trades"][0]
        position = payload["presets"]["balanced"]["open_positions"][0]

        self.assertEqual(
            set(trade),
            {
                "ticker",
                "entry_signal_date",
                "entry_date",
                "entry_price",
                "exit_signal_date",
                "exit_date",
                "exit_price",
                "exit_reason",
                "shares",
                "notional",
                "entry_cost",
                "exit_cost",
                "realized_pnl",
                "return_pct",
                "holding_days",
                "conviction",
                "signal_direction",
                "llm_direction",
                "llm_alignment",
            },
        )
        self.assertEqual(
            set(position),
            {
                "ticker",
                "entry_signal_date",
                "entry_date",
                "entry_price",
                "latest_date",
                "latest_close",
                "shares",
                "notional",
                "market_value",
                "unrealized_pnl",
                "return_pct",
                "holding_days",
                "conviction",
                "signal_direction",
                "llm_direction",
                "llm_alignment",
            },
        )
        self.assertAlmostEqual(trade["return_pct"], 17.673)
        self.assertAlmostEqual(position["return_pct"], 9.85)

    def test_later_avoid_exits_next_trading_day_open(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=80),
                signal("AAA", "2026-01-03", "avoid", conviction=20),
            ],
            [
                price("AAA", "2026-01-02", 100, 101, 99, 100),
                price("AAA", "2026-01-04", 105, 106, 104, 105),
            ],
        )

        trade = payload["presets"]["balanced"]["trades"][0]

        self.assertEqual(trade["exit_signal_date"], "2026-01-03")
        self.assertEqual(trade["exit_date"], "2026-01-04")
        self.assertEqual(trade["exit_reason"], "avoid")
        self.assertAlmostEqual(trade["exit_price"], 105.0)

    def test_llm_diagnostics_counts_aligned_conflict_missing(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=90, signal_direction="bull", llm_direction="bull"),
                signal("BBB", "2026-01-01", "buy", conviction=80, signal_direction="bull", llm_direction="bear"),
                signal("CCC", "2026-01-01", "buy", conviction=70, signal_direction="neutral", llm_direction=None),
            ],
            [
                price("AAA", "2026-01-02", 100, 120, 99, 119),
                price("BBB", "2026-01-02", 100, 101, 99, 100),
                price("CCC", "2026-01-02", 100, 101, 99, 100),
            ],
        )

        diagnostics = payload["presets"]["balanced"]["llm_direction_diagnostics"]

        self.assertEqual(diagnostics["aligned"]["trade_count"], 1)
        self.assertEqual(diagnostics["aligned"]["closed_trade_count"], 1)
        self.assertEqual(diagnostics["conflict"]["trade_count"], 1)
        self.assertEqual(diagnostics["conflict"]["open_position_count"], 1)
        self.assertEqual(diagnostics["missing"]["trade_count"], 1)
        self.assertEqual(diagnostics["missing"]["open_position_count"], 1)

    def test_summary_equity_curve_and_pnl_metrics_are_aggregated(self) -> None:
        payload = build_strategy_simulator(
            [
                signal("AAA", "2026-01-01", "buy", conviction=90, signal_direction="bull", llm_direction="bull"),
                signal("BBB", "2026-01-01", "buy", conviction=80, signal_direction="bull", llm_direction="bull"),
            ],
            [
                price("AAA", "2026-01-02", 100, 118, 99, 118),
                price("BBB", "2026-01-02", 100, 101, 99, 100),
                price("BBB", "2026-01-03", 100, 101, 99, 110),
            ],
        )

        balanced = payload["presets"]["balanced"]
        summary = balanced["summary"]
        last_curve = balanced["equity_curve"][-1]

        self.assertEqual(summary["trade_count"], 2)
        self.assertEqual(summary["closed_trade_count"], 1)
        self.assertEqual(summary["open_position_count"], 1)
        self.assertEqual(summary["winning_trade_count"], 1)
        self.assertEqual(summary["losing_trade_count"], 0)
        self.assertAlmostEqual(summary["win_rate"], 1.0)
        self.assertAlmostEqual(summary["realized_pnl"], 1767.3)
        self.assertAlmostEqual(summary["unrealized_pnl"], 984.85225)
        self.assertAlmostEqual(summary["ending_equity"], 102752.15225)
        self.assertAlmostEqual(summary["total_return_pct"], 2.75215225)
        self.assertAlmostEqual(last_curve["realized_pnl"], summary["realized_pnl"])
        self.assertAlmostEqual(last_curve["unrealized_pnl"], summary["unrealized_pnl"])
        self.assertEqual(last_curve["open_position_count"], 1)
        self.assertAlmostEqual(balanced["trades"][0]["return_pct"], 17.673)
        self.assertAlmostEqual(balanced["open_positions"][0]["return_pct"], 9.85)
        self.assertAlmostEqual(
            balanced["llm_direction_diagnostics"]["aligned"]["avg_trade_return_pct"],
            13.7615,
        )


if __name__ == "__main__":
    unittest.main()
