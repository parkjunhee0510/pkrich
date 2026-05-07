from __future__ import annotations

import unittest
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.analyzer.ensemble import EnsembleResult
from src.analyzer.committee import default_committee_analysis
from src.pipeline import _run_committee_flow, _run_sector_scan, run_pipeline
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision, WatchlistItem
from src.utils.model_config import CommitteeConfig


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


def _patch_search_evidence_hooks(stack: ExitStack):
    mock_collect_search_evidence = stack.enter_context(
        patch("src.pipeline.collect_search_evidence", return_value={"schema_version": 1, "items": []})
    )
    mock_write_search_evidence = stack.enter_context(patch("src.pipeline.write_search_evidence_output"))
    return mock_collect_search_evidence, mock_write_search_evidence


def _run_minimal_pipeline_for_sector_tests(
    *,
    with_sectors: bool,
    recorded_events: list[tuple[str, str, str, dict[str, object]]],
):
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
    ensemble_result = EnsembleResult(
        analyses=[_analysis("AAPL")],
        economy_analyses_by_ticker={"AAPL": _analysis("AAPL")},
        deep_analyses_by_ticker={},
        consensus_by_ticker={},
        quality_summary_by_ticker={},
        portfolio_result={"portfolio_risk": {}},
        diagnostics={},
        final_decisions=[_decision("AAPL")],
    )

    def _record_event(component, level, event, **fields):
        recorded_events.append((component, level, event, fields))

    with ExitStack() as stack:
        stack.enter_context(patch("src.pipeline.load_dotenv"))
        stack.enter_context(patch("src.pipeline.start_pipeline_logging"))
        stack.enter_context(patch("src.pipeline.record_pipeline_event", side_effect=_record_event))
        stack.enter_context(patch("src.pipeline.finalize_pipeline_logging"))
        stack.enter_context(patch("src.pipeline.load_watchlist", return_value=watchlist))
        stack.enter_context(patch("src.pipeline.load_portfolio", return_value=[]))
        mock_datastore_factory = stack.enter_context(patch("src.pipeline.get_datastore"))
        stack.enter_context(
            patch("src.pipeline._collect_market_context", return_value=(collected, date(2026, 4, 29), [], [], {}))
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
        mock_collect_search_evidence, mock_write_search_evidence = _patch_search_evidence_hooks(stack)
        stack.enter_context(patch("src.pipeline.build_weekly_ab_test_payload", return_value={}))
        stack.enter_context(patch("src.pipeline.write_ab_test_results"))
        mock_sector_scan = stack.enter_context(patch("src.pipeline._run_sector_scan"))
        stack.enter_context(patch("src.pipeline.send_daily_summary"))
        stack.enter_context(patch("src.pipeline.evaluate_alert_rules", return_value=[]))
        stack.enter_context(patch("src.pipeline.send_signal_alerts"))
        stack.enter_context(patch("src.pipeline.write_analysis_quality_output"))
        stack.enter_context(patch("src.pipeline.write_cost_log_output"))
        stack.enter_context(patch("src.pipeline.write_routing_outcome_output"))
        stack.enter_context(patch("src.pipeline.write_api_status_outputs"))
        stack.enter_context(patch("src.pipeline._write_validation_warnings_json"))
        stack.enter_context(patch("src.pipeline.run_policy_stage", return_value=None))
        stack.enter_context(patch("src.pipeline.generate_decisions", return_value=[_decision("AAPL")]))
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

        run_pipeline(run_date=date(2026, 4, 29), with_sectors=with_sectors)

    return mock_sector_scan, mock_collect_search_evidence, mock_write_search_evidence


class PipelineQualityWiringTests(unittest.TestCase):
    def test_run_sector_scan_syncs_web_public_mirror_after_write(self) -> None:
        watchlist = [WatchlistItem(ticker="AAPL", name="Apple")]

        with ExitStack() as stack:
            stack.enter_context(patch("src.pipeline.load_sectors", return_value={"Technology": []}))
            stack.enter_context(patch("src.pipeline.scan_sectors", return_value=[]))
            stack.enter_context(patch("src.pipeline.write_sectors_json", return_value=Path("output/data/sectors.json")))
            stack.enter_context(patch("src.pipeline.record_pipeline_event"))
            mock_sync = stack.enter_context(patch("src.pipeline._sync_web_public_data"))

            _run_sector_scan(watchlist, date(2026, 5, 4))

        mock_sync.assert_called_once_with(Path("output") / "data", Path("."))

    def test_run_pipeline_skips_sector_scan_by_default_and_logs_skip(self) -> None:
        events: list[tuple[str, str, str, dict[str, object]]] = []

        mock_sector_scan, _mock_collect_search_evidence, _mock_write_search_evidence = _run_minimal_pipeline_for_sector_tests(
            with_sectors=False,
            recorded_events=events,
        )

        mock_sector_scan.assert_not_called()
        self.assertIn(
            (
                "pipeline",
                "info",
                "sector_scan_skipped",
                {
                    "reason": "disabled_by_default",
                    "hint": "run with --with-sectors to refresh sectors.json",
                },
            ),
            events,
        )

    def test_run_pipeline_runs_sector_scan_when_requested(self) -> None:
        events: list[tuple[str, str, str, dict[str, object]]] = []

        mock_sector_scan, _mock_collect_search_evidence, _mock_write_search_evidence = _run_minimal_pipeline_for_sector_tests(
            with_sectors=True,
            recorded_events=events,
        )

        mock_sector_scan.assert_called_once()
        self.assertFalse(any(event == "sector_scan_skipped" for *_prefix, event, _fields in events))

    def test_run_pipeline_writes_search_evidence_output(self) -> None:
        events: list[tuple[str, str, str, dict[str, object]]] = []

        _mock_sector_scan, mock_collect_search_evidence, mock_write_search_evidence = _run_minimal_pipeline_for_sector_tests(
            with_sectors=False,
            recorded_events=events,
        )

        mock_collect_search_evidence.assert_called_once()
        kwargs = mock_collect_search_evidence.call_args.kwargs
        self.assertEqual(kwargs["run_date"], date(2026, 4, 29))
        self.assertEqual(kwargs["tickers"], ["AAPL"])
        mock_write_search_evidence.assert_called_once_with(
            {"schema_version": 1, "items": []},
            output_root=Path("output"),
        )

    def test_run_pipeline_writes_api_status_for_calendar_run_date(self) -> None:
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

        with ExitStack() as stack:
            stack.enter_context(patch("src.pipeline.load_dotenv"))
            stack.enter_context(patch("src.pipeline.start_pipeline_logging"))
            stack.enter_context(patch("src.pipeline.record_pipeline_event"))
            stack.enter_context(patch("src.pipeline.finalize_pipeline_logging"))
            stack.enter_context(patch("src.pipeline.load_watchlist", return_value=watchlist))
            stack.enter_context(patch("src.pipeline.load_portfolio", return_value=[]))
            mock_datastore_factory = stack.enter_context(patch("src.pipeline.get_datastore"))
            stack.enter_context(
                patch("src.pipeline._collect_market_context", return_value=(collected, date(2026, 4, 28), [], [], {}))
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
            _patch_search_evidence_hooks(stack)
            stack.enter_context(patch("src.pipeline.build_weekly_ab_test_payload", return_value={}))
            stack.enter_context(patch("src.pipeline.write_ab_test_results"))
            stack.enter_context(patch("src.pipeline._run_sector_scan"))
            stack.enter_context(patch("src.pipeline.send_daily_summary"))
            stack.enter_context(patch("src.pipeline.evaluate_alert_rules", return_value=[]))
            stack.enter_context(patch("src.pipeline.send_signal_alerts"))
            stack.enter_context(patch("src.pipeline.write_analysis_quality_output"))
            stack.enter_context(patch("src.pipeline.write_cost_log_output"))
            stack.enter_context(patch("src.pipeline.write_routing_outcome_output"))
            mock_write_api_status = stack.enter_context(patch("src.pipeline.write_api_status_outputs"))
            stack.enter_context(patch("src.pipeline._write_validation_warnings_json"))
            stack.enter_context(patch("src.pipeline.generate_decisions", return_value=[_decision("AAPL")]))
            stack.enter_context(
                patch("src.pipeline.apply_consensus_to_decisions", side_effect=lambda decisions, _consensus: decisions)
            )
            datastore = mock_datastore_factory.return_value
            datastore.load_recent_signals_data.return_value = []
            datastore.load_signal_stats_data.return_value = {}
            datastore.update_signal_returns.return_value = 0
            datastore.record_signals.return_value = None
            datastore.record_analysis_run.return_value = None
            mock_build_ensemble.return_value.analyze_with_consensus.return_value = EnsembleResult(
                analyses=[_analysis("AAPL")],
                economy_analyses_by_ticker={"AAPL": _analysis("AAPL")},
                deep_analyses_by_ticker={},
                consensus_by_ticker={},
                quality_summary_by_ticker={},
                portfolio_result={"portfolio_risk": {}},
                diagnostics={},
                final_decisions=[_decision("AAPL")],
            )

            run_pipeline(run_date=date(2026, 4, 29))

        self.assertEqual(mock_write_api_status.call_args.args[0], date(2026, 4, 29))

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
            _patch_search_evidence_hooks(stack)
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

    def test_run_pipeline_attaches_committee_analysis_before_serialization(self) -> None:
        watchlist = [WatchlistItem(ticker="AAPL", name="Apple"), WatchlistItem(ticker="MSFT", name="Microsoft")]
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
            ),
            "MSFT": CollectedTickerData(
                ticker="MSFT",
                name="Microsoft",
                sector="Technology",
                price=200.0,
                change_percent=1.0,
                currency="USD",
                market_cap="2T",
                pe_ratio="30",
                summary_note="",
            ),
        }
        analyses = [_analysis("AAPL"), _analysis("MSFT")]
        ensemble_result = EnsembleResult(
            analyses=analyses,
            economy_analyses_by_ticker={"AAPL": _analysis("AAPL"), "MSFT": _analysis("MSFT")},
            deep_analyses_by_ticker={},
            consensus_by_ticker={},
            quality_summary_by_ticker={},
            portfolio_result={"portfolio_risk": {}},
            diagnostics={},
            final_decisions=[_decision("AAPL"), _decision("MSFT")],
        )
        captured: dict[str, object] = {}

        def _capture_generate_decisions(*args, **kwargs):
            captured["decision_analyses"] = list(args[0])
            return [_decision("AAPL"), _decision("MSFT")]

        def _capture_write_outputs(analyses_arg, *args, **kwargs):
            captured["output_analyses"] = list(analyses_arg)
            return {}

        committee_config = CommitteeConfig(
            enabled=True,
            economy_model="economy",
            deep_model="deep",
            pm_low_confidence_threshold=0.55,
            max_summary_sentences_per_role=2,
            max_summary_sentences_for_pm=3,
        )

        def _committee_runner(analysis, *, committee_config=None, path="config/models.yaml", run_role=None):
            if analysis.ticker == "AAPL":
                return {
                    "status": "deep_reviewed",
                    "agreement_status": "aligned",
                    "deep_review_triggered": True,
                    "deep_review_reasons": ["pm_low_confidence"],
                    "roles": {"pm": {"role": "pm", "round": "deep", "profile": "deep", "stance": "buy", "action": "buy", "confidence": 0.42, "strong_objection": False, "summary": "pm"}},
                }
            raise RuntimeError("committee unavailable")

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
            stack.enter_context(patch("src.pipeline.write_outputs", side_effect=_capture_write_outputs))
            _patch_search_evidence_hooks(stack)
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
            stack.enter_context(patch("src.pipeline.load_committee_config", return_value=committee_config))
            stack.enter_context(patch("src.pipeline.run_committee_analysis", side_effect=_committee_runner))
            datastore = mock_datastore_factory.return_value
            datastore.load_recent_signals_data.return_value = []
            datastore.load_signal_stats_data.return_value = {}
            datastore.update_signal_returns.return_value = 0
            datastore.record_signals.return_value = None
            datastore.record_analysis_run.return_value = None
            mock_build_ensemble.return_value.analyze_with_consensus.return_value = ensemble_result

            run_pipeline(run_date=date(2026, 4, 23))

        committee_aapl = next(item for item in captured["output_analyses"] if item.ticker == "AAPL")
        committee_msft = next(item for item in captured["output_analyses"] if item.ticker == "MSFT")
        self.assertEqual(committee_aapl.committee_analysis["status"], "deep_reviewed")
        self.assertEqual(committee_msft.committee_analysis["status"], "economy_only")
        self.assertEqual(committee_msft.committee_analysis["roles"], {})
        self.assertEqual(captured["decision_analyses"][0].committee_analysis["status"], "deep_reviewed")
        self.assertEqual(captured["decision_analyses"][1].committee_analysis["status"], "economy_only")

    def test_run_committee_flow_falls_back_on_malformed_payload(self) -> None:
        analysis = _analysis("AAPL")

        with ExitStack() as stack:
            stack.enter_context(patch("src.pipeline.load_committee_config", return_value=CommitteeConfig(
                enabled=True,
                economy_model="economy",
                deep_model="deep",
                pm_low_confidence_threshold=0.55,
                max_summary_sentences_per_role=2,
                max_summary_sentences_for_pm=3,
            )))
            stack.enter_context(patch("src.pipeline.record_pipeline_event"))
            stack.enter_context(
                patch(
                    "src.pipeline.run_committee_analysis",
                    return_value={"status": "deep_reviewed", "agreement_status": "aligned"},
                )
            )

            result = _run_committee_flow([analysis])

        self.assertEqual(result["AAPL"], default_committee_analysis())

    def test_run_committee_flow_skips_empty_inputs_before_config_load(self) -> None:
        with patch("src.pipeline.load_committee_config") as load_committee_config:
            result = _run_committee_flow([])

        self.assertEqual(result, {})
        load_committee_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
