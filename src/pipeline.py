from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path

from src.analyzer.modules import (
    NewsAnalysisModule,
    PeerComparisonModule,
    PortfolioRiskModule,
    ResearchNarrativeModule,
    RiskAssessmentModule,
    SignalTakeawayModule,
    TradeFrameModule,
    ValuationModule,
)
from src.analyzer.ab_test import build_weekly_ab_test_payload
from src.analyzer.committee import default_committee_analysis, run_committee_analysis
from src.analyzer.prompts import get_prompt_template
from src.analyzer.ensemble import AnalysisEnsemble
from src.analyzer.ensemble import apply_consensus_to_decisions
from src.analyzer.orchestrator import AnalysisOrchestrator
from src.analyzer.registry import ModuleRegistry
from src.analyzer.search_audit import build_search_audit_payload
from src.collector.macro import collect_macro_context
from src.utils.config import load_yaml_mapping
from src.collector.policy_events import extract_events
from src.analyzer.policy_impact import map_impacts
from src.output.policy_json import write_policy_impact_json
from src.output.policy_active_events import update_dossier, to_policy_events
from src.collector.peer_candidates import load_peer_candidates, persist_peer_selections
from src.decision.decision_layer import generate_decisions
from src.decision.market_regime import detect_market_regime
from src.decision.search_quality import attach_search_quality_shadow
from src.collector.news_rss import collect_news_for_watchlist
from src.collector.news_shadow_compare import run_news_shadow_comparison
from src.collector.orchestrated_collection import (
    collect_market_data_via_orchestrator,
    collect_news_via_orchestrator,
)
from src.collector.price import collect_market_data, collect_market_overview
from src.collector.search_evidence import collect_search_evidence
from src.collector.sector_scan import scan_sectors
from src.collector.shadow_compare import run_shadow_comparison
from src.output.alert import evaluate_alert_rules
from src.output.analysis_quality import write_analysis_quality_output
from src.output.api_status import write_api_status_outputs
from src.output.ab_test import write_ab_test_results
from src.output.cost_log import write_cost_log_output
from src.output.intraday_refresh import write_intraday_refresh_outputs
from src.output.markdown import write_outputs
from src.output.routing_outcome import write_routing_outcome_output
from src.output.schema import SCHEMA_VERSION
from src.output.search_audit_json import write_search_audit_output
from src.output.search_evidence_json import write_search_evidence_output
from src.output.sectors_json import write_sectors_json
from src.output.slack import send_daily_summary, send_pipeline_failure_alert, send_signal_alerts
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis
from src.utils.config import load_portfolio, load_sectors, load_watchlist
from src.utils.datastore import get_datastore
from src.utils.env import is_env_flag_enabled, load_dotenv
from src.utils.macro_sensitivity import attach_portfolio_macro_sensitivity
from src.utils.model_config import load_committee_config
from src.utils.portfolio import calculate_portfolio_summary
from src.utils.pipeline_logging import finalize_pipeline_logging, get_pipeline_logger, record_pipeline_event, start_pipeline_logging
from src.output.json_export import _sync_web_public_data, _write_validation_warnings_json


def _build_analysis_orchestrator(model_profile_name: str | None = None) -> AnalysisOrchestrator:
    registry = ModuleRegistry()
    registry.register_many(
        [
            PeerComparisonModule(),
            ValuationModule(),
            TradeFrameModule(),
            PortfolioRiskModule(),
            NewsAnalysisModule(),
            ResearchNarrativeModule(),
            RiskAssessmentModule(),
            SignalTakeawayModule(),
        ]
    )
    from src.utils.model_config import load_model_profile

    return AnalysisOrchestrator(
        registry=registry,
        model_profile=load_model_profile(profile_name=model_profile_name),
        logger=get_pipeline_logger(),
    )


def _build_analysis_ensemble() -> AnalysisEnsemble:
    from src.utils.model_config import load_ensemble_config, load_model_profile

    ensemble_config = load_ensemble_config()
    second_profile = load_model_profile(profile_name=ensemble_config.second_model)
    if ensemble_config.second_prompt:
        second_profile = replace(second_profile, prompt_version=ensemble_config.second_prompt)
    third_profile = load_model_profile(profile_name=ensemble_config.third_model)
    if ensemble_config.third_prompt:
        third_profile = replace(third_profile, prompt_version=ensemble_config.third_prompt)
    return AnalysisEnsemble(
        economy_orchestrator=_build_analysis_orchestrator(model_profile_name="economy"),
        deep_orchestrator=AnalysisOrchestrator(
            _build_analysis_orchestrator(model_profile_name=ensemble_config.second_model).registry,
            model_profile=second_profile,
            logger=get_pipeline_logger(),
        ),
        tie_break_orchestrator=AnalysisOrchestrator(
            _build_analysis_orchestrator(model_profile_name=ensemble_config.third_model).registry,
            model_profile=third_profile,
            logger=get_pipeline_logger(),
        ),
        config=ensemble_config,
    )


def run_policy_stage(
    today: str,
    ticker_ctx: dict,
    sources_config: dict,
    model_profile: str,
    category_to_sectors: dict,
    output_path: str = "output/data/policy_impact.json",
):
    """Run the two-stage policy pipeline with isolated try/except.

    Returns a PolicyImpactReport on success, None on any failure or empty events.
    Failures here MUST NOT propagate — the main pipeline keeps running with
    policy data treated as missing.
    """
    try:
        new_events = extract_events(
            today=today,
            model_profile=model_profile,
            sources_config=sources_config,
        )
        record_pipeline_event(
            "policy.collector", "info", "events_extracted",
            count=len(new_events),
        )
        if not new_events:
            return None
        # Plan B: merge into the rolling active-events dossier so
        # events stay in scope for up to 30 days with age-based decay.
        dossier_entries = update_dossier(new_events, today=today)
        record_pipeline_event(
            "policy.dossier", "info", "dossier_active",
            active=len(dossier_entries),
            new=len(new_events),
        )
        if not dossier_entries:
            return None
        active_events = to_policy_events(dossier_entries)
        event_weight_by_id = {
            entry["id"]: float(entry.get("decay_weight", 1.0))
            for entry in dossier_entries
        }
        report = map_impacts(
            events=active_events,
            ticker_ctx=ticker_ctx,
            category_to_sectors=category_to_sectors,
            model_profile=model_profile,
            today=today,
            event_weight_by_id=event_weight_by_id,
        )
        record_pipeline_event(
            "policy.analyzer", "info", "tickers_scored",
            count=len(report.tailwind_scores),
        )
        write_policy_impact_json(report, output_path)
        return report
    except Exception as exc:
        record_pipeline_event(
            "policy", "error", "policy_stage_failed",
            error=str(exc),
        )
        return None


def run_pipeline(run_date: date | None = None, *, with_sectors: bool = False) -> None:
    load_dotenv()
    calendar_run_date = run_date or date.today()
    effective_date = calendar_run_date
    start_pipeline_logging(effective_date)
    record_pipeline_event("pipeline", "info", "pipeline_started", run_date=effective_date.isoformat())

    success = False
    watchlist = []
    try:
        watchlist = load_watchlist()
        portfolio_holdings = load_portfolio()
        datastore = get_datastore(output_root=Path("output"))

        collected, effective_date, historical_price_rows, market_overview, macro_context = _collect_market_context(
            watchlist,
            effective_date,
            datastore,
        )

        # Phase 1-0e Step 5a: NewsOrchestrator primary dispatch.
        # When ENABLE_NEWS_ORCHESTRATOR_PRIMARY=true, the NewsOrchestrator
        # is the source of truth and legacy collect_news_for_watchlist()
        # is skipped. Default remains legacy until flag is flipped after
        # shadow-mode validation.
        news_orchestrator_primary = is_env_flag_enabled(
            "ENABLE_NEWS_ORCHESTRATOR_PRIMARY", default=False
        )
        if news_orchestrator_primary:
            news_map = collect_news_via_orchestrator(watchlist, effective_date)
        else:
            news_map = collect_news_for_watchlist(watchlist, effective_date)

        # Phase 1-0e Step 4-e: NewsOrchestrator shadow comparison.
        # Only meaningful in legacy-primary mode — the shadow path IS
        # what becomes primary when the flag flips.
        if (
            not news_orchestrator_primary
            and is_env_flag_enabled("ENABLE_NEWS_ORCHESTRATOR_SHADOW", default=False)
        ):
            run_news_shadow_comparison(watchlist, effective_date, news_map)
        portfolio_summary = calculate_portfolio_summary(portfolio_holdings, collected)
        macro_context = attach_portfolio_macro_sensitivity(
            macro_context,
            portfolio_summary,
            collected,
            watchlist,
        )
        portfolio_account_size = portfolio_summary.total_market_value if portfolio_summary else None
        signal_history_map = {
            item.ticker: datastore.load_recent_signals_data(item.ticker)
            for item in watchlist
        }
        peer_candidates_by_ticker = load_peer_candidates(
            watchlist,
            collected,
            effective_date,
            output_root=Path("output"),
        )
        market_regime = detect_market_regime(market_overview, macro_context, collected, effective_date)
        # Expose regime to downstream prompt builders via macro_context.
        if isinstance(macro_context, dict):
            macro_context["market_regime"] = {
                "regime": market_regime.regime,
                "sub_regime": getattr(market_regime, "sub_regime", ""),
                "confidence": market_regime.confidence,
                "implication": market_regime.implication,
                "drivers": dict(market_regime.drivers),
                "forward_signals": dict(getattr(market_regime, "forward_signals", {}) or {}),
            }
            # Build a run-level macro narrative (LLM synthesis, cached 24h).
            try:
                from src.analyzer.macro_narrative import build_macro_narrative
                macro_context["macro_narrative"] = build_macro_narrative(
                    macro_context, market_regime, effective_date
                )
            except Exception:
                record_pipeline_event("analyzer", "warning", "macro_narrative_failed")
        ensemble = _build_analysis_ensemble()
        ensemble_result = ensemble.analyze_with_consensus(
            watchlist,
            collected,
            news_map,
            effective_date,
            market_regime=market_regime,
            signal_stats=datastore.load_signal_stats_data(),
            macro_context=macro_context,
            signal_history_map=signal_history_map,
            portfolio_account_size=portfolio_account_size,
            portfolio_summary=portfolio_summary,
            portfolio_risk={},
            peer_candidates_by_ticker=peer_candidates_by_ticker,
        )
        analyses = ensemble_result.analyses
        committee_analyses_by_ticker = _run_committee_flow(analyses)
        analyses = [
            replace(
                analysis,
                committee_analysis=committee_analyses_by_ticker.get(
                    analysis.ticker,
                    default_committee_analysis(),
                ),
            )
            for analysis in analyses
        ]
        portfolio_risk: dict[str, object] = ensemble_result.portfolio_result.get("portfolio_risk", {})
        persist_peer_selections(ensemble.economy_orchestrator.diagnostics, effective_date, output_root=Path("output"))
        _persist_routing_log(ensemble.config, ensemble_result.diagnostics, Path("output"))
        price_lookup = {ticker: data.price for ticker, data in collected.items() if data.price is not None}
        updated_signals = datastore.update_signal_returns(
            effective_date,
            price_lookup,
            price_history_rows=historical_price_rows,
        )
        # Triple-barrier labeling (Phase A Task 2) — additive; runs alongside
        # classical return_Nd fill so both outcome models coexist.
        try:
            from src.utils.signal_tracker import update_triple_barrier_labels
            barrier_updated = update_triple_barrier_labels(
                datastore.data_dir / "signal_tracker.csv",
                effective_date,
                price_history_rows=historical_price_rows,
            )
            record_pipeline_event(
                "decision.triple_barrier", "info", "barrier_labels_updated",
                updated=barrier_updated,
            )
        except Exception as exc:
            record_pipeline_event(
                "decision.triple_barrier", "error", "barrier_labeling_error",
                error=str(exc),
            )
        signal_stats = datastore.load_signal_stats_data()

        # Policy/regulation impact stage (Task 8). Isolated — failures
        # never propagate, factor 9 simply sees missing data.
        sources_cfg = load_yaml_mapping("config/policy_sources.yaml", optional=True) or {}
        ticker_policy_ctx = load_yaml_mapping("config/ticker_policy_context.yaml", optional=True) or {}
        # Auto-synthesize stub context for watchlist tickers missing from
        # ticker_policy_context.yaml so policy coverage tracks the watchlist
        # automatically. Hand-curated entries (richer metadata) always win.
        for _wl_item in watchlist:
            if _wl_item.ticker not in ticker_policy_ctx:
                ticker_policy_ctx[_wl_item.ticker] = {
                    "sector": (_wl_item.sector or "").lower().replace(" ", "_") or "other",
                    "business": _wl_item.name,
                    "exposure": list(getattr(_wl_item, "keywords", []) or []),
                    "china_revenue_pct": 0,
                }
                record_pipeline_event(
                    "policy", "info", "ticker_ctx_synthesized",
                    ticker=_wl_item.ticker,
                )
        policy_report = run_policy_stage(
            today=effective_date.isoformat(),
            ticker_ctx=ticker_policy_ctx,
            sources_config=sources_cfg,
            model_profile=str(sources_cfg.get("model_profile", "deep")),
            category_to_sectors=sources_cfg.get("category_to_sectors", {}) or {},
        )
        if policy_report is not None and isinstance(signal_stats, dict):
            signal_stats["_policy_tailwind_scores"] = dict(policy_report.tailwind_scores)
            signal_stats["_policy_impacts_by_ticker"] = {
                t: list(impacts) for t, impacts in policy_report.impacts_by_ticker.items()
            }

        # Decision layer: market regime + per-ticker decisions
        try:
            decisions = apply_consensus_to_decisions(
                generate_decisions(
                    analyses,
                    collected,
                    market_regime,
                    signal_stats,
                    effective_date,
                    analysis_consensus_by_ticker=ensemble_result.consensus_by_ticker,
                    quality_summary_by_ticker=ensemble_result.quality_summary_by_ticker,
                    portfolio_risk=portfolio_risk,
                    macro_context=macro_context,
                ),
                ensemble_result.consensus_by_ticker,
            )
            record_pipeline_event(
                "decision", "info", "decision_completed",
                regime=market_regime.regime,
                confidence=market_regime.confidence,
                decisions_count=len(decisions),
                ensemble_enabled=ensemble_result.diagnostics.get("ensemble_enabled", False),
                ensemble_eligible_count=len(ensemble_result.diagnostics.get("eligible_tickers", [])),
                ensemble_selected_count=len(ensemble_result.diagnostics.get("selected_tickers", [])),
                ensemble_skipped_due_to_cap=len(ensemble_result.diagnostics.get("skipped_due_to_cap", [])),
                ensemble_conflicted_count=len(ensemble_result.diagnostics.get("third_review_tickers", [])),
            )
        except Exception:
            market_regime = MarketRegime()
            decisions = []
            record_pipeline_event("decision", "warning", "decision_failed")

        search_evidence_payload = _collect_search_evidence_artifact(effective_date, analyses)
        decisions = attach_search_quality_shadow(decisions, search_evidence_payload)

        datastore.record_signals(
            analyses,
            effective_date,
            price_lookup,
            decisions=decisions,
            market_regime=market_regime,
        )
        signal_stats = datastore.load_signal_stats_data()

        direct_period_changes = {
            ticker: {"7d": data.price_change_7d, "30d": data.price_change_30d}
            for ticker, data in collected.items()
        }
        state_metadata = {
            "decision_signal_stats_as_of": effective_date.isoformat(),
            "decision_signal_stats_includes_current_run": False,
            "output_signal_stats_as_of": effective_date.isoformat(),
            "output_signal_stats_includes_current_run": True,
            "signal_returns_updated_before_decision": True,
        }
        output_paths = write_outputs(
            analyses,
            effective_date,
            market_overview=market_overview,
            direct_period_changes=direct_period_changes,
            portfolio_summary=portfolio_summary,
            signal_stats=signal_stats,
            macro_context=macro_context,
            portfolio_risk=portfolio_risk,
            market_regime=market_regime,
            decisions=decisions,
            state_metadata=state_metadata,
        )
        _write_search_evidence_artifact(effective_date, analyses, search_evidence_payload)
        ab_test_payload = build_weekly_ab_test_payload(
            run_date=calendar_run_date,
            watchlist=watchlist,
            collected=collected,
            news_map=news_map,
            analyses=analyses,
            variant_a=get_prompt_template("research_v1", "signal_takeaway_module"),
            variant_b=get_prompt_template("research_v2", "signal_takeaway_module"),
            output_root=Path("output"),
        )
        write_ab_test_results(ab_test_payload, output_root=Path("output"))
        if with_sectors:
            _run_sector_scan(watchlist, effective_date)
        else:
            record_pipeline_event(
                "pipeline",
                "info",
                "sector_scan_skipped",
                reason="disabled_by_default",
                hint="run with --with-sectors to refresh sectors.json",
            )
        send_daily_summary(
            analyses,
            effective_date,
            market_overview=market_overview,
            daily_note_path=output_paths.get("daily_path"),
            weekly_note_path=output_paths.get("weekly_path"),
            portfolio_summary=portfolio_summary,
            macro_context=macro_context,
        )
        signal_alerts = evaluate_alert_rules(watchlist, collected)
        send_signal_alerts(signal_alerts)
        success = True
        record_pipeline_event("pipeline", "info", "pipeline_completed", ticker_count=len(analyses), updated_signal_rows=updated_signals)
        datastore.record_analysis_run(run_date=effective_date, success=True, logger=get_pipeline_logger())
    except Exception as exc:
        send_pipeline_failure_alert(effective_date, str(exc))
        record_pipeline_event(
            "pipeline",
            "error",
            "pipeline_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        get_datastore(output_root=Path("output")).record_analysis_run(
            run_date=effective_date,
            success=False,
            logger=get_pipeline_logger(),
        )
        raise
    finally:
        finalize_pipeline_logging(success)
        _write_validation_warnings_json(Path("output") / "data")
        write_analysis_quality_output(output_root=Path("output"), logs_root=Path("logs") / "pipeline")
        write_cost_log_output(output_root=Path("output"), logs_root=Path("logs") / "pipeline")
        write_routing_outcome_output(output_root=Path("output"))
        if watchlist:
            write_api_status_outputs(calendar_run_date, watchlist, output_root=Path("output"))


def collect_only(run_date: date | None = None) -> dict[str, object]:
    load_dotenv()
    calendar_run_date = run_date or date.today()
    effective_date = calendar_run_date
    start_pipeline_logging(effective_date)
    record_pipeline_event("pipeline", "info", "collect_only_started", run_date=effective_date.isoformat())

    success = False
    try:
        watchlist = load_watchlist()
        portfolio_holdings = load_portfolio()
        datastore = get_datastore(output_root=Path("output"))
        collected, effective_date, _historical_price_rows, market_overview, macro_context = _collect_market_context(
            watchlist,
            effective_date,
            datastore,
        )
        datastore.upsert_collected_prices(collected, effective_date)
        portfolio_summary = calculate_portfolio_summary(portfolio_holdings, collected)
        macro_context = attach_portfolio_macro_sensitivity(
            macro_context,
            portfolio_summary,
            collected,
            watchlist,
        )
        refresh_payload = write_intraday_refresh_outputs(
            collected,
            effective_date,
            market_overview=market_overview,
            macro_context=macro_context,
            portfolio_summary=portfolio_summary,
            output_root=Path("output"),
        )
        success = True
        record_pipeline_event(
            "pipeline",
            "info",
            "collect_only_completed",
            run_date=effective_date.isoformat(),
            ticker_count=len(collected),
        )
        return refresh_payload
    except Exception as exc:
        send_pipeline_failure_alert(effective_date, str(exc))
        record_pipeline_event(
            "pipeline",
            "error",
            "collect_only_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise
    finally:
        finalize_pipeline_logging(success)


def _persist_routing_log(
    ensemble_config,
    diagnostics: dict,
    output_root: Path,
) -> None:
    if not getattr(ensemble_config, "emit_routing_log", False):
        return
    routing_log = diagnostics.get("routing_log")
    if not routing_log:
        return
    import json as _json

    data_dir = output_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    latest_path = data_dir / "routing_log.json"
    latest_path.write_text(
        _json.dumps(routing_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    history_path = data_dir / "routing_log_history.json"
    history_payload = {
        "schema_version": SCHEMA_VERSION,
        "runs": [],
    }
    if history_path.exists():
        try:
            existing = _json.loads(history_path.read_text(encoding="utf-8"))
        except _json.JSONDecodeError:
            existing = {}
        if isinstance(existing, dict):
            runs = existing.get("runs", [])
            if isinstance(runs, list):
                history_payload["runs"] = [run for run in runs if isinstance(run, dict)]

    run_date = str(routing_log.get("run_date", "")).strip()
    filtered_runs = [
        run for run in history_payload["runs"]
        if str(run.get("run_date", "")).strip() != run_date
    ]
    filtered_runs.append(routing_log)
    filtered_runs.sort(key=lambda item: str(item.get("run_date", "")))
    history_payload["runs"] = filtered_runs[-90:]
    history_path.write_text(
        _json.dumps(history_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _collect_search_evidence_artifact(effective_date: date, analyses: list[TickerAnalysis]) -> dict[str, object] | None:
    try:
        return collect_search_evidence(
            run_date=effective_date,
            tickers=[analysis.ticker for analysis in analyses],
        )
    except Exception as exc:
        record_pipeline_event(
            "pipeline",
            "warning",
            "search_evidence_collect_failed",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
        return None


def _write_search_evidence_artifact(
    effective_date: date,
    analyses: list[TickerAnalysis],
    payload: dict[str, object] | None,
) -> None:
    if payload is None:
        return

    try:
        write_search_evidence_output(payload, output_root=Path("output"))
        record_pipeline_event(
            "pipeline",
            "info",
            "search_evidence_output_written",
            ticker_count=len(payload.get("by_ticker", {})),
            item_count=len(payload.get("items", [])),
        )
    except Exception as exc:
        record_pipeline_event(
            "pipeline",
            "warning",
            "search_evidence_output_failed",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
        return

    try:
        audit_payload = build_search_audit_payload(
            run_date=effective_date,
            analyses=analyses,
            search_evidence=payload,
        )
        write_search_audit_output(audit_payload, output_root=Path("output"))
        record_pipeline_event(
            "pipeline",
            "info",
            "search_audit_output_written",
            ticker_count=len(audit_payload.get("tickers", [])),
            issue_count=int(audit_payload.get("run_summary", {}).get("issue_count", 0)),
        )
    except Exception as exc:
        record_pipeline_event(
            "pipeline",
            "warning",
            "search_audit_output_failed",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )


def _collect_market_context(
    watchlist,
    effective_date: date,
    datastore,
):
    orchestrator_primary = is_env_flag_enabled(
        "ENABLE_ORCHESTRATOR_PRIMARY", default=True
    )
    if orchestrator_primary:
        collected = collect_market_data_via_orchestrator(watchlist, effective_date)
    else:
        collected = collect_market_data(watchlist, effective_date)
        if is_env_flag_enabled("ENABLE_ORCHESTRATOR_SHADOW", default=False):
            run_shadow_comparison(watchlist, effective_date, collected)

    market_date = _detect_actual_market_date(collected, fallback=effective_date)
    if market_date != effective_date:
        record_pipeline_event(
            "pipeline", "info", "market_date_adjusted",
            run_date=effective_date.isoformat(),
            market_date=market_date.isoformat(),
        )
        effective_date = market_date
    collected = _filter_historical_prices_to_market_date(collected, effective_date)
    historical_price_rows = datastore.query_prices(tickers=[item.ticker for item in watchlist])
    collected = _merge_missing_prices_from_history(collected, historical_price_rows)
    market_overview = collect_market_overview()
    vix_data = _extract_vix_from_overview(market_overview)
    macro_context = collect_macro_context(effective_date, vix_data=vix_data)
    return collected, effective_date, historical_price_rows, market_overview, macro_context


def _extract_vix_from_overview(market_overview: list[dict[str, str]]) -> dict[str, str] | None:
    for entry in market_overview:
        if entry.get("label") == "VIX" or entry.get("symbol") == "^VIX":
            return {
                "price": entry.get("price", "N/A"),
                "change_percent": entry.get("change_percent", "N/A"),
            }
    return None


def _filter_historical_prices_to_market_date(
    collected: dict[str, CollectedTickerData],
    market_date: date,
) -> dict[str, CollectedTickerData]:
    """Remove historical_prices rows dated after market_date.

    yfinance may include today's premarket rows under today's date even
    before the session opens. Stripping them prevents storing incomplete
    data and avoids duplicate entries in price_history exports.
    """
    cutoff = market_date.isoformat()
    result = {}
    for ticker, data in collected.items():
        clean = [row for row in data.historical_prices if row.get("date", "") <= cutoff]
        result[ticker] = replace(data, historical_prices=clean) if len(clean) != len(data.historical_prices) else data
    return result


def _detect_actual_market_date(
    collected: dict[str, CollectedTickerData],
    fallback: date,
) -> date:
    """Return the most recent trading date found in collected price history.

    yfinance returns the last available close, which may be the previous
    trading day when the pipeline runs before US market open. Using the
    actual date from the data avoids storing duplicate entries under the
    wrong (run) date.
    """
    latest: date | None = None
    for data in collected.values():
        for row in data.historical_prices:
            try:
                row_date = date.fromisoformat(row["date"])
                if latest is None or row_date > latest:
                    latest = row_date
            except (KeyError, ValueError):
                continue
    return latest if latest is not None else fallback


def _merge_missing_prices_from_history(
    collected: dict[str, CollectedTickerData],
    historical_price_rows: list[dict[str, str]],
) -> dict[str, CollectedTickerData]:
    latest_price_by_ticker: dict[str, float] = {}
    latest_date_by_ticker: dict[str, str] = {}
    for row in historical_price_rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        row_date = str(row.get("date", "")).strip()
        price_value = _parse_price_value(row.get("price", ""))
        if not ticker or price_value is None or not row_date:
            continue
        previous_date = latest_date_by_ticker.get(ticker, "")
        if previous_date and previous_date >= row_date:
            continue
        latest_date_by_ticker[ticker] = row_date
        latest_price_by_ticker[ticker] = price_value

    patched = dict(collected)
    for ticker, payload in patched.items():
        price = getattr(payload, "price", None)
        if price is not None:
            continue
        fallback_price = latest_price_by_ticker.get(ticker)
        if fallback_price is None:
            continue
        patched[ticker] = replace(payload, price=fallback_price)
    return patched


def _parse_price_value(raw_value: object) -> float | None:
    text = str(raw_value or "").strip().replace(",", "")
    if not text or text == "N/A":
        return None
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _run_sector_scan(watchlist, effective_date) -> None:
    """Scan sector explorer tickers (price + news only). Isolated so a sector
    outage cannot fail the whole pipeline — logged and swallowed."""
    try:
        sectors_config = load_sectors()
        if not sectors_config:
            return
        watchlist_tickers = {item.ticker.upper() for item in watchlist}
        snapshots = scan_sectors(
            sectors_config,
            effective_date,
            skip_tickers=watchlist_tickers,
        )
        write_sectors_json(snapshots, effective_date, output_root=Path("output"))
        _sync_web_public_data(Path("output") / "data", Path("."))
        record_pipeline_event(
            "pipeline",
            "info",
            "sector_scan_completed",
            sector_count=len(snapshots),
        )
    except Exception as exc:  # defensive — decoupled from main flow
        record_pipeline_event(
            "pipeline",
            "warning",
            "sector_scan_failed",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )


def _run_committee_flow(analyses):
    if not analyses:
        return {}

    committee_config = load_committee_config()
    committee_results: dict[str, dict[str, object]] = {}
    for analysis in analyses:
        try:
            committee_result = run_committee_analysis(analysis, committee_config=committee_config)
        except Exception as exc:
            record_pipeline_event(
                "analyzer",
                "warning",
                "committee_analysis_failed",
                ticker=getattr(analysis, "ticker", ""),
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            committee_result = default_committee_analysis()
        if not _is_valid_committee_payload(committee_result):
            record_pipeline_event(
                "analyzer",
                "warning",
                "committee_payload_invalid",
                ticker=getattr(analysis, "ticker", ""),
            )
            committee_result = default_committee_analysis()
        committee_results[getattr(analysis, "ticker", "")] = committee_result
    return committee_results


def _is_valid_committee_payload(payload) -> bool:
    if not isinstance(payload, dict):
        return False
    required_keys = {"status", "agreement_status", "deep_review_triggered", "deep_review_reasons", "roles"}
    return required_keys.issubset(payload.keys())
