from __future__ import annotations

import unittest

from src.collector.search_evidence_priority import build_priority_refresh_plan


class SearchEvidencePriorityTests(unittest.TestCase):
    def test_orders_router_pool_by_evidence_gap_context_and_router_tie_breaker(self) -> None:
        plan = build_priority_refresh_plan(
            tickers=["AAPL", "AMD", "COHR", "MSFT"],
            router_priority_tickers=["AAPL", "AMD", "COHR"],
            mode="openai",
            cached_tickers={"AAPL"},
            stale_cache_tickers={"AAPL"},
            priority_context_by_ticker={
                "AAPL": {"in_portfolio": True, "action": "watch", "change_percent": 1.2},
                "AMD": {"action": "buy", "change_percent": 8.3},
                "COHR": {"action": "watch", "change_percent": 1.0},
            },
        )

        self.assertEqual(plan.priority_tickers, ["AMD", "COHR", "AAPL"])
        self.assertEqual(
            plan.reasons_by_ticker["AMD"],
            ["router_selected", "no_evidence", "important_action", "high_volatility"],
        )
        self.assertEqual(plan.reasons_by_ticker["COHR"], ["router_selected", "no_evidence"])
        self.assertEqual(
            plan.reasons_by_ticker["AAPL"],
            ["router_selected", "stale_cache", "portfolio_holding"],
        )
        self.assertNotIn("MSFT", plan.reasons_by_ticker)
        self.assertEqual(plan.reason_counts["router_selected"], 3)
        self.assertEqual(plan.reason_counts["no_evidence"], 2)
        self.assertEqual(plan.reason_counts["stale_cache"], 1)
        self.assertEqual(plan.reason_counts["portfolio_holding"], 1)
        self.assertEqual(plan.reason_counts["important_action"], 1)
        self.assertEqual(plan.reason_counts["high_volatility"], 1)

    def test_cache_mode_marks_uncached_priority_tickers_as_not_refreshed(self) -> None:
        plan = build_priority_refresh_plan(
            tickers=["AAPL", "AMD"],
            router_priority_tickers=["AMD", "AAPL"],
            mode="cache",
            cached_tickers=set(),
            priority_context_by_ticker={
                "AAPL": {"action": "avoid"},
                "AMD": {"action": "watch"},
            },
        )

        self.assertEqual(plan.priority_tickers, ["AAPL", "AMD"])
        self.assertEqual(
            plan.reasons_by_ticker["AAPL"],
            ["router_selected", "not_refreshed", "important_action"],
        )
        self.assertEqual(plan.reasons_by_ticker["AMD"], ["router_selected", "not_refreshed"])
        self.assertEqual(plan.reason_counts["not_refreshed"], 2)
        self.assertEqual(plan.reason_counts["important_action"], 1)

    def test_normalizes_deduplicates_and_keeps_router_order_for_equal_scores(self) -> None:
        plan = build_priority_refresh_plan(
            tickers=["aapl", "AMD", "COHR"],
            router_priority_tickers=[" amd ", "AAPL", "AMD", "missing"],
            mode="openai",
            cached_tickers=set(),
            priority_context_by_ticker={},
        )

        self.assertEqual(plan.priority_tickers, ["AMD", "AAPL"])
        self.assertEqual(plan.reasons_by_ticker["AMD"], ["router_selected", "no_evidence"])
        self.assertEqual(plan.reasons_by_ticker["AAPL"], ["router_selected", "no_evidence"])
        self.assertNotIn("COHR", plan.reasons_by_ticker)

    def test_set_router_priority_tickers_use_sorted_order_for_equal_scores(self) -> None:
        plan = build_priority_refresh_plan(
            tickers=["AAPL", "AMD", "COHR"],
            router_priority_tickers={"AMD", "AAPL", "COHR"},
            mode="openai",
            cached_tickers=set(),
            priority_context_by_ticker={},
        )

        self.assertEqual(plan.priority_tickers, ["AAPL", "AMD", "COHR"])


if __name__ == "__main__":
    unittest.main()
