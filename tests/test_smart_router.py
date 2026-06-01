from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.smart_router import (
    build_router_scores,
    estimate_deep_review_cost,
    rank_router_candidates,
)
from src.types import CollectedTickerData, TickerAnalysis, TickerDecision, WatchlistItem
from src.utils.model_config import ModelProfile


def _decision(
    ticker: str,
    conviction: int,
    *,
    action: str = "watch",
    confidence_meta: dict[str, object] | None = None,
) -> TickerDecision:
    return TickerDecision(
        ticker=ticker,
        action=action,
        conviction=conviction,
        reason="",
        confidence_meta=confidence_meta or {},
    )


def _collected(ticker: str, *, change_percent: float = 0.0) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=ticker,
        sector="Technology",
        price=100.0,
        change_percent=change_percent,
        currency="USD",
        market_cap="100B",
        pe_ratio="20",
        summary_note="",
    )


def _analysis(ticker: str, *, upcoming_events: list[dict[str, str]] | None = None) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        name=ticker,
        date="2026-05-12",
        summary="summary",
        key_news=[],
        news_references=[],
        financial_highlights=[],
        risks_or_watchpoints=[],
        signal_or_takeaway="signal",
        data_snapshot={},
        upcoming_events=upcoming_events or [],
    )


def _watchlist(tickers: list[str]) -> list[WatchlistItem]:
    return [WatchlistItem(ticker=ticker, name=ticker) for ticker in tickers]


class SmartRouterTests(unittest.TestCase):
    def test_boundary_proximity_ranks_near_buy_watch_boundary_first(self) -> None:
        watchlist = _watchlist(["KO", "AMD"])
        scores = build_router_scores(
            watchlist,
            {
                "KO": _decision("KO", 52),
                "AMD": _decision("AMD", 67),
            },
            collected_by_ticker={ticker: _collected(ticker) for ticker in ["KO", "AMD"]},
        )

        ranked = rank_router_candidates(["KO", "AMD"], scores, watchlist)

        self.assertEqual(ranked, ["AMD", "KO"])
        self.assertIn("uncertainty_boundary", scores["AMD"]["reason_codes"])
        self.assertGreater(scores["AMD"]["priority_score"], scores["KO"]["priority_score"])

    def test_portfolio_exposure_and_event_proximity_add_reason_codes(self) -> None:
        watchlist = _watchlist(["AAPL", "MSFT"])
        scores = build_router_scores(
            watchlist,
            {
                "AAPL": _decision("AAPL", 50),
                "MSFT": _decision("MSFT", 50),
            },
            analyses_by_ticker={
                "AAPL": _analysis("AAPL"),
                "MSFT": _analysis("MSFT", upcoming_events=[{"date": "2026-05-18"}]),
            },
            collected_by_ticker={ticker: _collected(ticker) for ticker in ["AAPL", "MSFT"]},
            portfolio_tickers={"AAPL"},
            run_date=date(2026, 5, 12),
        )

        ranked = rank_router_candidates(["AAPL", "MSFT"], scores, watchlist)

        self.assertEqual(ranked[0], "AAPL")
        self.assertIn("portfolio_exposure", scores["AAPL"]["reason_codes"])
        self.assertIn("event_proximity", scores["MSFT"]["reason_codes"])

    def test_evidence_gap_volatility_and_signal_importance_add_reason_codes(self) -> None:
        watchlist = _watchlist(["AMD"])
        scores = build_router_scores(
            watchlist,
            {
                "AMD": _decision(
                    "AMD",
                    67,
                    action="buy",
                    confidence_meta={"search_evidence_score": 0.25},
                ),
            },
            collected_by_ticker={"AMD": _collected("AMD", change_percent=7.5)},
        )

        reason_codes = scores["AMD"]["reason_codes"]

        self.assertIn("evidence_gap", reason_codes)
        self.assertIn("volatility", reason_codes)
        self.assertIn("signal_importance", reason_codes)

    def test_estimate_deep_review_cost_reports_incremental_and_monthly_cost(self) -> None:
        profile = ModelProfile(
            name="deep",
            model="test-model",
            prompt_version="research_v2",
            context_window=200000,
            max_output_tokens=100000,
            monthly_cost_estimate_usd=8.0,
            input_cost_per_1m_tokens=1.0,
            cached_input_cost_per_1m_tokens=0.5,
            output_cost_per_1m_tokens=4.0,
        )

        estimate = estimate_deep_review_cost(profile, selected_count=3, trading_days_per_month=20)

        self.assertEqual(estimate["selected_count"], 3)
        self.assertGreater(estimate["estimated_incremental_cost_usd"], 0)
        self.assertEqual(
            estimate["estimated_monthly_cost_usd"],
            round(estimate["estimated_incremental_cost_usd"] * 20, 4),
        )


if __name__ == "__main__":
    unittest.main()
