from __future__ import annotations

import unittest
from contextlib import ExitStack
from datetime import date
from unittest.mock import patch

from src.analyzer.ensemble import EnsembleResult
from src.pipeline import run_pipeline
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision, WatchlistItem


def _analysis(ticker: str) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=ticker,
        name=f"{ticker} Inc.",
        date="2026-04-23",
        summary="summary",
        key_news=[],
        news_references=[],
        financial_highlights=[],
        risks_or_watchpoints=[],
        signal_or_takeaway="signal",
        data_snapshot={"Price": "100"},
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


def _decision(ticker: str) -> TickerDecision:
    return TickerDecision(ticker=ticker, action="watch", conviction=50, reason="reason")


class PipelineQualityWiringTests(unittest.TestCase):
    def test_run_pipeline_passes_consensus_and_quality_summaries_into_decision_generation(self) -> None:
        watchlist = [WatchlistItem(ticker="AAPL", name="Apple")]
        collected = {
            "AAPL": CollectedTickerData(
                ticker="AAPL",
                name="Apple",
                sector="Technology",
                price=100.0,
                change_percent=1.0,
                currency="USD",
                market_cap="1T",
                pe_ratio="20",
                summary_note="",
            )
        }
        consensus_by_ticker = {"AAPL": {"status": "agreed", "final_consensus": "agree"}}
        quality_summary_by_ticker = {"AAPL": {"fact_warning_count": 1, "fallback_used": False}}
        ensemble_result = EnsembleResult(
            analyses=[_analysis("AAPL")],
            economy_analyses_by_ticker={"AAPL": _analysis("AAPL")},
            deep_analyses_by_ticker={},
            consensus_by_ticker=consensus_by_ticker,
            quality_summary_by_ticker=quality_summary_by_ticker,
            portfolio_result={"portfolio_risk": {}},
            diagnostics={},
            final_decisions=[_decision("AAPL")],
        )
        captured: dict[str, object] = {}

        def _capture_generate_decisions(*args, **kwargs):
            captured["analysis_consensus_by_ticker"] = kwargs.get("analysis_consensus_by_ticker")
            captured["quality_summary_by_ticker"] = kwargs.get("quality_summary_by_ticker")
            return [_decision("AAPL")]

        with ExitStack() as stack:
            stack.enter_context(patch("src.pipeline.load_dotenv"))
            stack.enter_context(patch("src.pipeline.start_pipeline_logging"))
            stack.enter_context(patch("src.pipeline.record_pipeline_event"))
            stack.enter_context(patch("src.pipeline.finalize_pipeline_logging"))
            stack.enter_context(patch("src.pipeline.load_watchlist", return_value=watchlist))
            stack.enter_context(patch("src.pipeline.load_portfolio", return_value=[]))
            mock_datastore_factory = stack.enter_context(patch("src.pipeline.get_datastore"))
            stack.enter_context(
                patch("src.pipeline._collect_market_context", return_value=(collected, date(2026, 4, 23), [], [], {}))
            )
            stack.enter_context(patch("src.pipeline.collect_news_for_watchlist", return_value={}))
            stack.enter_context(patch("src.pipeline.calculate_portfolio_summary", return_value=None))
            stack.enter_context(
                patch("src.pipeline.attach_portfolio_macro_sensitivity", side_effect=lambda macro, *_args: macro)
            )
            stack.enter_context(patch("src.pipeline.load_peer_candidates", return_value={}))
            stack.enter_context(patch("src.pipeline.detect_market_regime", return_value=MarketRegime()))
            mock_build_ensemble = stack.enter_context(patch("src.pipeline._build_analysis_ensemble"))
            stack.enter_context(patch("src.pipeline.persist_peer_selections"))
            stack.enter_context(patch("src.pipeline._persist_routing_log"))
            stack.enter_context(patch("src.pipeline.write_outputs", return_value={}))
            stack.enter_context(patch("src.pipeline.build_weekly_ab_test_payload", return_value={}))
            stack.enter_context(patch("src.pipeline.write_ab_test_results"))
            stack.enter_context(patch("src.pipeline._run_sector_scan"))
            stack.enter_context(patch("src.pipeline.send_daily_summary"))
            stack.enter_context(patch("src.pipeline.evaluate_alert_rules", return_value=[]))
            stack.enter_context(patch("src.pipeline.send_signal_alerts"))
            stack.enter_context(patch("src.pipeline.write_analysis_quality_output"))
            stack.enter_context(patch("src.pipeline.write_cost_log_output"))
            stack.enter_context(patch("src.pipeline.write_routing_outcome_output"))
            stack.enter_context(patch("src.pipeline.write_api_status_outputs"))
            stack.enter_context(patch("src.pipeline._write_validation_warnings_json"))
            stack.enter_context(patch("src.pipeline.generate_decisions", side_effect=_capture_generate_decisions))
            stack.enter_context(
                patch("src.pipeline.apply_consensus_to_decisions", side_effect=lambda decisions, _consensus: decisions)
            )
            datastore = mock_datastore_factory.return_value
            datastore.load_recent_signals_data.return_value = []
            datastore.load_signal_stats_data.return_value = {}
            datastore.update_signal_returns.return_value = 0
            datastore.record_signals.return_value = None
            datastore.record_analysis_run.return_value = None
            mock_build_ensemble.return_value.analyze_with_consensus.return_value = ensemble_result

            run_pipeline(run_date=date(2026, 4, 23))

        self.assertEqual(captured["analysis_consensus_by_ticker"], consensus_by_ticker)
        self.assertEqual(captured["quality_summary_by_ticker"], quality_summary_by_ticker)


if __name__ == "__main__":
    unittest.main()
