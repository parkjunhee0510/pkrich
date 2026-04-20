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
            EnsembleConfig(
                enabled=True,
                trigger_range=(25, 75),
                second_model="deep",
                second_prompt="research_v2",
                max_daily_ensemble=1,
            ),
        )
        decisions_sequence = [
            [
                TickerDecision(ticker="AAPL", action="buy", conviction=82, reason="economy 강세"),
                TickerDecision(ticker="KO", action="watch", conviction=52, reason="economy 중립"),
                TickerDecision(ticker="AMD", action="buy", conviction=67, reason="economy 긍정"),
            ],
            [
                TickerDecision(ticker="AMD", action="buy", conviction=70, reason="deep 긍정"),
            ],
            [
                TickerDecision(ticker="AAPL", action="buy", conviction=82, reason="economy 강세"),
                TickerDecision(ticker="KO", action="watch", conviction=52, reason="economy 중립"),
                TickerDecision(ticker="AMD", action="buy", conviction=70, reason="deep 긍정"),
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
            EnsembleConfig(
                enabled=False,
                trigger_range=(25, 75),
                second_model="deep",
                second_prompt="research_v2",
                max_daily_ensemble=5,
            ),
        )

        with patch(
            "src.analyzer.ensemble.generate_decisions",
            side_effect=[
                [TickerDecision(ticker="AAPL", action="watch", conviction=50, reason="economy 중립")],
                [TickerDecision(ticker="AAPL", action="watch", conviction=50, reason="economy 중립")],
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

    def test_apply_consensus_to_decisions_appends_conflict_reason(self) -> None:
        decisions = [TickerDecision(ticker="AAPL", action="avoid", conviction=32, reason="deep 보수")]
        updated = apply_consensus_to_decisions(
            decisions,
            {
                "AAPL": {
                    "status": "conflicted",
                    "economy_action": "buy",
                    "economy_reason": "economy 강세",
                }
            },
        )
        self.assertIn("합의 불일치", updated[0].reason)
        self.assertIn("economy는 buy 관점", updated[0].reason)


if __name__ == "__main__":
    unittest.main()
