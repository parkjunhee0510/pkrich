from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.ensemble import AnalysisEnsemble, apply_consensus_to_decisions
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision, WatchlistItem
from src.utils.model_config import EnsembleConfig


def _make_collected(ticker: str) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=f"{ticker} Inc.",
        sector="Technology",
        price=100.0,
        change_percent=1.0,
        currency="USD",
        market_cap="100B",
        pe_ratio="20",
        summary_note="",
    )


def _make_analysis(ticker: str, *, summary: str, signal: str) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        name=f"{ticker} Inc.",
        date="2026-04-16",
        summary=summary,
        key_news=[],
        news_references=[],
        financial_highlights=[],
        risks_or_watchpoints=[],
        signal_or_takeaway=signal,
        data_snapshot={},
        fundamentals={},
        price_action={},
        quarterly_financials=[],
        upcoming_events=[],
        news_tone={},
        trade_frame={},
        options_summary={},
        signal_history=[],
        sector_comparison={},
        peer_rank={},
        valuation_score={},
        historical_prices=[],
    )


class _FakeOrchestrator:
    def __init__(self, full_results: list[TickerAnalysis], llm_only_results: list[TickerAnalysis] | None = None) -> None:
        self.full_results = full_results
        self.llm_only_results = llm_only_results or []
        self.calls: list[dict[str, object]] = []
        self.diagnostics: dict[str, object] = {}
        self.portfolio_result: dict[str, object] = {"portfolio_risk": {"risk_grade": "B"}}

    def analyze_all(self, watchlist, collected, news_map, run_date, **kwargs):
        del collected, news_map, run_date
        self.calls.append(
            {
                "tickers": [item.ticker for item in watchlist],
                "execution_mode": kwargs.get("execution_mode", "full"),
            }
        )
        self.diagnostics = {"executed_modules": ["news_analysis_module", "research_narrative_module"]}
        if kwargs.get("execution_mode") == "llm_only":
            return self.llm_only_results
        return self.full_results


def _config(*, enabled: bool = True, max_daily_ensemble: int = 0) -> EnsembleConfig:
    return EnsembleConfig(
        enabled=enabled,
        trigger_range=(25, 75),
        second_model="deep",
        second_prompt="research_v2",
        third_model="standard",
        third_prompt="research_v1",
        max_daily_ensemble=max_daily_ensemble,
    )


class AnalysisEnsembleTests(unittest.TestCase):
    def test_ensemble_selects_only_in_range_and_respects_cap(self) -> None:
        economy_orchestrator = _FakeOrchestrator(
            [
                _make_analysis("AAPL", summary="economy-aapl", signal="watch"),
                _make_analysis("KO", summary="economy-ko", signal="watch"),
                _make_analysis("AMD", summary="economy-amd", signal="watch"),
            ]
        )
        deep_orchestrator = _FakeOrchestrator(
            [],
            llm_only_results=[_make_analysis("AMD", summary="deep-amd", signal="buy")],
        )
        ensemble = AnalysisEnsemble(
            economy_orchestrator,
            deep_orchestrator,
            _FakeOrchestrator([]),
            _config(max_daily_ensemble=1),
        )
        decisions_sequence = [
            [
                TickerDecision(ticker="AAPL", action="buy", conviction=82, reason="economy strong"),
                TickerDecision(ticker="KO", action="watch", conviction=52, reason="economy neutral"),
                TickerDecision(ticker="AMD", action="buy", conviction=67, reason="economy positive"),
            ],
            [
                TickerDecision(ticker="AMD", action="buy", conviction=70, reason="deep positive"),
            ],
            [
                TickerDecision(ticker="AAPL", action="buy", conviction=82, reason="economy strong"),
                TickerDecision(ticker="KO", action="watch", conviction=52, reason="economy neutral"),
                TickerDecision(ticker="AMD", action="buy", conviction=70, reason="deep positive"),
            ],
        ]

        with patch("src.analyzer.ensemble.generate_decisions", side_effect=decisions_sequence):
            result = ensemble.analyze_with_consensus(
                [
                    WatchlistItem(ticker="AAPL", name="Apple"),
                    WatchlistItem(ticker="KO", name="Coke"),
                    WatchlistItem(ticker="AMD", name="AMD"),
                ],
                {"AAPL": _make_collected("AAPL"), "KO": _make_collected("KO"), "AMD": _make_collected("AMD")},
                {},
                date(2026, 4, 16),
                market_regime=MarketRegime(regime="neutral"),
            )

        self.assertEqual(result.diagnostics["eligible_tickers"], ["KO", "AMD"])
        self.assertEqual(result.diagnostics["selected_tickers"], ["AMD"])
        self.assertEqual(result.diagnostics["skipped_due_to_cap"], ["KO"])
        self.assertEqual(deep_orchestrator.calls[0]["execution_mode"], "llm_only")
        self.assertEqual(deep_orchestrator.calls[0]["tickers"], ["AMD"])
        self.assertEqual(result.consensus_by_ticker["AAPL"]["selection_reason"], "out_of_range")
        self.assertEqual(result.consensus_by_ticker["KO"]["selection_reason"], "cap_exceeded")
        self.assertEqual(result.consensus_by_ticker["AMD"]["status"], "agreed")
        final_amd = next(item for item in result.analyses if item.ticker == "AMD")
        self.assertEqual(final_amd.summary, "deep-amd")

    def test_ensemble_disabled_skips_deep_reanalysis(self) -> None:
        economy_orchestrator = _FakeOrchestrator([_make_analysis("AAPL", summary="economy-aapl", signal="watch")])
        deep_orchestrator = _FakeOrchestrator([], llm_only_results=[_make_analysis("AAPL", summary="deep-aapl", signal="buy")])
        ensemble = AnalysisEnsemble(
            economy_orchestrator,
            deep_orchestrator,
            _FakeOrchestrator([]),
            _config(enabled=False, max_daily_ensemble=5),
        )

        with patch(
            "src.analyzer.ensemble.generate_decisions",
            side_effect=[
                [TickerDecision(ticker="AAPL", action="watch", conviction=50, reason="economy neutral")],
                [TickerDecision(ticker="AAPL", action="watch", conviction=50, reason="economy neutral")],
            ],
        ):
            result = ensemble.analyze_with_consensus(
                [WatchlistItem(ticker="AAPL", name="Apple")],
                {"AAPL": _make_collected("AAPL")},
                {},
                date(2026, 4, 16),
                market_regime=MarketRegime(regime="neutral"),
            )

        self.assertEqual(deep_orchestrator.calls, [])
        self.assertFalse(result.diagnostics["ensemble_enabled"])
        self.assertEqual(result.consensus_by_ticker["AAPL"]["selection_reason"], "disabled")

    def test_zero_cap_means_unlimited_selection(self) -> None:
        economy_orchestrator = _FakeOrchestrator(
            [
                _make_analysis("AAPL", summary="economy-aapl", signal="watch"),
                _make_analysis("KO", summary="economy-ko", signal="watch"),
                _make_analysis("AMD", summary="economy-amd", signal="watch"),
            ]
        )
        deep_orchestrator = _FakeOrchestrator(
            [],
            llm_only_results=[
                _make_analysis("KO", summary="deep-ko", signal="buy"),
                _make_analysis("AMD", summary="deep-amd", signal="buy"),
            ],
        )
        third_orchestrator = _FakeOrchestrator(
            [],
            llm_only_results=[_make_analysis("KO", summary="third-ko", signal="watch")],
        )
        ensemble = AnalysisEnsemble(
            economy_orchestrator,
            deep_orchestrator,
            third_orchestrator,
            _config(max_daily_ensemble=0),
        )

        decisions_sequence = [
            [
                TickerDecision(ticker="AAPL", action="buy", conviction=82, reason="economy strong"),
                TickerDecision(ticker="KO", action="watch", conviction=52, reason="economy neutral"),
                TickerDecision(ticker="AMD", action="buy", conviction=67, reason="economy positive"),
            ],
            [
                TickerDecision(ticker="KO", action="buy", conviction=58, reason="deep positive"),
                TickerDecision(ticker="AMD", action="buy", conviction=70, reason="deep positive"),
            ],
            [
                TickerDecision(ticker="KO", action="watch", conviction=54, reason="third tie-break"),
            ],
            [
                TickerDecision(ticker="AAPL", action="buy", conviction=82, reason="economy strong"),
                TickerDecision(ticker="KO", action="watch", conviction=54, reason="third tie-break"),
                TickerDecision(ticker="AMD", action="buy", conviction=70, reason="deep positive"),
            ],
        ]

        with patch("src.analyzer.ensemble.generate_decisions", side_effect=decisions_sequence):
            result = ensemble.analyze_with_consensus(
                [
                    WatchlistItem(ticker="AAPL", name="Apple"),
                    WatchlistItem(ticker="KO", name="Coke"),
                    WatchlistItem(ticker="AMD", name="AMD"),
                ],
                {"AAPL": _make_collected("AAPL"), "KO": _make_collected("KO"), "AMD": _make_collected("AMD")},
                {},
                date(2026, 4, 16),
                market_regime=MarketRegime(regime="neutral"),
            )

        self.assertEqual(result.diagnostics["eligible_tickers"], ["KO", "AMD"])
        self.assertEqual(result.diagnostics["selected_tickers"], ["AMD", "KO"])
        self.assertEqual(result.diagnostics["skipped_due_to_cap"], [])
        self.assertEqual(deep_orchestrator.calls[0]["tickers"], ["KO", "AMD"])
        self.assertEqual(third_orchestrator.calls[0]["tickers"], ["KO"])

    def test_conflict_runs_third_review_and_marks_resolved_consensus(self) -> None:
        economy_orchestrator = _FakeOrchestrator([_make_analysis("AAPL", summary="economy-aapl", signal="buy")])
        deep_orchestrator = _FakeOrchestrator([], llm_only_results=[_make_analysis("AAPL", summary="deep-aapl", signal="avoid")])
        third_orchestrator = _FakeOrchestrator([], llm_only_results=[_make_analysis("AAPL", summary="third-aapl", signal="buy")])
        ensemble = AnalysisEnsemble(
            economy_orchestrator,
            deep_orchestrator,
            third_orchestrator,
            _config(max_daily_ensemble=0),
        )

        decisions_sequence = [
            [TickerDecision(ticker="AAPL", action="buy", conviction=60, reason="economy positive")],
            [TickerDecision(ticker="AAPL", action="avoid", conviction=38, reason="deep cautious")],
            [TickerDecision(ticker="AAPL", action="buy", conviction=62, reason="third confirms buy")],
            [TickerDecision(ticker="AAPL", action="buy", conviction=62, reason="third confirms buy")],
        ]

        with patch("src.analyzer.ensemble.generate_decisions", side_effect=decisions_sequence):
            result = ensemble.analyze_with_consensus(
                [WatchlistItem(ticker="AAPL", name="Apple")],
                {"AAPL": _make_collected("AAPL")},
                {},
                date(2026, 4, 16),
                market_regime=MarketRegime(regime="neutral"),
            )

        self.assertEqual(third_orchestrator.calls[0]["execution_mode"], "llm_only")
        self.assertEqual(result.diagnostics["conflicted_tickers"], ["AAPL"])
        self.assertEqual(result.diagnostics["third_review_tickers"], ["AAPL"])
        self.assertEqual(result.consensus_by_ticker["AAPL"]["third_action"], "buy")
        self.assertTrue(result.consensus_by_ticker["AAPL"]["third_review_completed"])
        self.assertEqual(result.consensus_by_ticker["AAPL"]["final_consensus"], "resolved")
        self.assertEqual(result.final_decisions[0].final_consensus, "resolved")
        self.assertIn("3차 검토로 최종 합의", result.final_decisions[0].reason)

    def test_apply_consensus_to_decisions_appends_conflict_reason(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="avoid", conviction=32, reason="deep defensive")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "status": "conflicted",
                    "economy_action": "buy",
                    "economy_reason": "economy strong",
                }
            },
        )
        self.assertIn("합의 불일치", updated[0].reason)
        self.assertIn("buy", updated[0].reason)


class ConvictionAdjustmentTests(unittest.TestCase):
    def test_agree_tight_spread_boosts_full_amount(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="buy", conviction=70, reason="")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "final_consensus": "agree",
                    "economy_conviction": 72,
                    "deep_conviction": 70,
                    "third_conviction": 71,
                },
            },
        )
        # mean ~= 71, stdev very small → +8 boost → ~79
        self.assertGreater(updated[0].conviction, 75)
        self.assertLessEqual(updated[0].conviction, 80)
        self.assertIn("앙상블 보정", updated[0].reason)

    def test_agree_wide_spread_shrinks_boost(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="buy", conviction=60, reason="")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "final_consensus": "agree",
                    "economy_conviction": 40,
                    "deep_conviction": 80,
                },
            },
        )
        # mean = 60, stdev = 20 → boost = max(0, 8 - 0.5*20) = 0 → stays at 60
        self.assertEqual(updated[0].conviction, 60)

    def test_resolved_caps_at_median(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="buy", conviction=80, reason="")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "final_consensus": "resolved",
                    "economy_conviction": 80,
                    "deep_conviction": 30,
                    "third_conviction": 65,
                },
            },
        )
        # median = 65 → capped
        self.assertEqual(updated[0].conviction, 65)

    def test_conflict_compresses_toward_fifty(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="buy", conviction=80, reason="")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "final_consensus": "conflict",
                    "economy_conviction": 80,
                    "deep_conviction": 80,
                    "third_conviction": 80,
                },
            },
        )
        # mean = 80 → adjusted = 50 + (80-50)*0.6 = 68
        self.assertEqual(updated[0].conviction, 68)

    def test_single_leaves_conviction_unchanged(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="buy", conviction=55, reason="")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "final_consensus": "single",
                    "economy_conviction": 55,
                },
            },
        )
        self.assertEqual(updated[0].conviction, 55)
        self.assertNotIn("앙상블 보정", updated[0].reason)

    def test_adjustment_diagnostics_written_to_consensus(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="buy", conviction=60, reason="")]
        consensus_map = {
            "AAPL": {
                "final_consensus": "agree",
                "economy_conviction": 60,
                "deep_conviction": 62,
            },
        }
        apply_consensus_to_decisions(decisions, consensus_map)
        payload = consensus_map["AAPL"]
        self.assertIn("conviction_mean", payload)
        self.assertIn("conviction_stdev", payload)
        self.assertIn("conviction_adjusted", payload)
        self.assertEqual(payload["conviction_prior"], 60)
        self.assertEqual(payload["conviction_sample_size"], 2)


if __name__ == "__main__":
    unittest.main()
