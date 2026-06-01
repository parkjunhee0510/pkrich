from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.ensemble import (
    _classify_routing_reason,
    _is_ensemble_target,
    _select_target_tickers,
    build_routing_log,
)
from src.types import TickerDecision, WatchlistItem
from src.utils.model_config import EnsembleConfig


def _config(**overrides) -> EnsembleConfig:
    base = dict(
        enabled=True,
        trigger_range=(25, 75),
        second_model="deep",
        second_prompt="research_v2",
        third_model="standard",
        third_prompt="research_v1",
        max_daily_ensemble=5,
        portfolio_priority=False,
        emit_routing_log=True,
    )
    base.update(overrides)
    return EnsembleConfig(**base)


def _decision(ticker: str, conviction: int, action: str = "watch") -> TickerDecision:
    return TickerDecision(
        ticker=ticker,
        action=action,
        conviction=conviction,
        reason="",
        valid_until="",
        factors={},
    )


def _watchlist(tickers: list[str]) -> list[WatchlistItem]:
    return [WatchlistItem(ticker=t, name=t) for t in tickers]


class EnsembleRoutingTests(unittest.TestCase):
    def test_in_trigger_range_is_target(self) -> None:
        self.assertTrue(_is_ensemble_target(_decision("A", 50), _config()))

    def test_outside_range_skipped_without_portfolio_priority(self) -> None:
        self.assertFalse(_is_ensemble_target(_decision("A", 10), _config()))
        self.assertFalse(_is_ensemble_target(_decision("A", 90), _config()))

    def test_portfolio_priority_overrides_range(self) -> None:
        cfg = _config(portfolio_priority=True)
        self.assertTrue(_is_ensemble_target(_decision("A", 10), cfg, in_portfolio=True))
        self.assertTrue(_is_ensemble_target(_decision("A", 95), cfg, in_portfolio=True))
        self.assertFalse(_is_ensemble_target(_decision("A", 10), cfg, in_portfolio=False))

    def test_select_ranks_portfolio_first(self) -> None:
        cfg = _config(portfolio_priority=True, max_daily_ensemble=2)
        watchlist = _watchlist(["A", "B", "C"])
        decisions = {
            "A": _decision("A", 50),
            "B": _decision("B", 55),
            "C": _decision("C", 10),
        }
        selected = _select_target_tickers(
            ["A", "B", "C"],
            decisions,
            watchlist,
            cfg,
            portfolio_tickers={"C"},
        )
        self.assertEqual(selected[0], "C")
        self.assertEqual(len(selected), 2)

    def test_cap_zero_is_unlimited(self) -> None:
        cfg = _config(max_daily_ensemble=0)
        watchlist = _watchlist(["A", "B", "C"])
        decisions = {t: _decision(t, 50) for t in ["A", "B", "C"]}
        selected = _select_target_tickers(["A", "B", "C"], decisions, watchlist, cfg)
        self.assertEqual(set(selected), {"A", "B", "C"})

    def test_select_uses_router_scores_when_available(self) -> None:
        cfg = _config(max_daily_ensemble=1)
        watchlist = _watchlist(["A", "B"])
        decisions = {"A": _decision("A", 50), "B": _decision("B", 50)}

        selected = _select_target_tickers(
            ["A", "B"],
            decisions,
            watchlist,
            cfg,
            router_scores={
                "A": {"priority_score": 10.0},
                "B": {"priority_score": 25.0},
            },
        )

        self.assertEqual(selected, ["B"])

    def test_classify_reason_covers_all_cases(self) -> None:
        cfg = _config()
        self.assertEqual(_classify_routing_reason(None, cfg, in_portfolio=False), "no_decision")
        self.assertEqual(_classify_routing_reason(_decision("A", 10), cfg, in_portfolio=False), "below_range")
        self.assertEqual(_classify_routing_reason(_decision("A", 90), cfg, in_portfolio=False), "above_range")
        self.assertEqual(_classify_routing_reason(_decision("A", 50), cfg, in_portfolio=False), "in_trigger_range")

        cfg2 = _config(portfolio_priority=True)
        self.assertEqual(_classify_routing_reason(_decision("A", 10), cfg2, in_portfolio=True), "portfolio_priority")

    def test_build_routing_log_shape(self) -> None:
        cfg = _config(portfolio_priority=True, max_daily_ensemble=1)
        watchlist = _watchlist(["A", "B"])
        decisions = {"A": _decision("A", 50), "B": _decision("B", 10)}
        log = build_routing_log(
            watchlist,
            decisions,
            target_tickers=["A"],
            config=cfg,
            portfolio_tickers={"B"},
            run_date=date(2026, 4, 17),
            router_scores={
                "A": {"priority_score": 12.0, "reason_codes": ["uncertainty_boundary"]},
                "B": {"priority_score": 30.0, "reason_codes": ["portfolio_exposure"]},
            },
            skipped_due_to_priority=["B"],
            router_budget_estimate={
                "selected_count": 1,
                "estimated_incremental_cost_usd": 0.0123,
                "estimated_monthly_cost_usd": 0.2706,
            },
        )
        self.assertEqual(log["schema_version"], 1)
        self.assertEqual(log["run_date"], "2026-04-17")
        self.assertEqual(log["portfolio_priority"], True)
        self.assertEqual(log["deep_pass_count"], 1)
        self.assertEqual(log["skipped_due_to_priority"], ["B"])
        self.assertEqual(log["router_budget_estimate"]["selected_count"], 1)
        a_entry = next(e for e in log["tickers"] if e["ticker"] == "A")
        b_entry = next(e for e in log["tickers"] if e["ticker"] == "B")
        self.assertTrue(a_entry["selected_for_deep"])
        self.assertFalse(b_entry["selected_for_deep"])
        self.assertTrue(b_entry["in_portfolio"])
        self.assertEqual(b_entry["reason"], "portfolio_priority")
        self.assertEqual(a_entry["router_priority_score"], 12.0)
        self.assertEqual(a_entry["router_reason_codes"], ["uncertainty_boundary"])
        self.assertFalse(a_entry["skipped_due_to_priority"])
        self.assertTrue(b_entry["skipped_due_to_priority"])


if __name__ == "__main__":
    unittest.main()
