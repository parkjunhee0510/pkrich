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
from src.analyzer.prompts import get_prompt_template
from dataclasses import replace

from src.analyzer.ensemble import AnalysisEnsemble
from src.analyzer.ensemble import apply_consensus_to_decisions
from src.analyzer.orchestrator import AnalysisOrchestrator
from src.analyzer.registry import ModuleRegistry
from src.collector.macro import collect_macro_context
from src.collector.peer_candidates import load_peer_candidates, persist_peer_selections
from src.decision.decision_layer import generate_decisions
from src.decision.market_regime import detect_market_regime
from src.collector.news_rss import collect_news_for_watchlist
from src.collector.news_shadow_compare import run_news_shadow_comparison
from src.collector.orchestrated_collection import (
    collect_market_data_via_orchestrator,
    collect_news_via_orchestrator,
)
from src.collector.price import collect_market_data, collect_market_overview
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
from src.output.sectors_json import write_sectors_json
from src.output.slack import send_daily_summary, send_pipeline_failure_alert, send_signal_alerts
from src.types import CollectedTickerData, MarketRegime
from src.utils.config import load_portfolio, load_sectors, load_watchlist
from src.utils.datastore import get_datastore
from src.utils.env import is_env_flag_enabled, load_dotenv
from src.utils.macro_sensitivity import attach_portfolio_macro_sensitivity
from src.utils.portfolio import calculate_portfolio_summary
from src.utils.pipeline_logging import finalize_pipeline_logging, get_pipeline_logger, record_pipeline_event, start_pipeline_logging
from src.output.json_export import _write_validation_warnings_json


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


def run_pipeline(run_date: date | None = None) -> None:
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
        )
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
        _run_sector_scan(watchlist, effective_date)
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
            write_api_status_outputs(effective_date, watchlist, output_root=Path("output"))


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
