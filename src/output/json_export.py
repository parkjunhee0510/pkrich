"""Export dashboard and timeline data as JSON for the React frontend."""
from __future__ import annotations

import csv
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from src.analyzer.derive import (
    build_backtest_summary,
    build_earnings_pattern,
    build_earnings_setup,
    build_earnings_surprise_summary,
    build_ticker_timelines,
    collect_sec_filing_tags,
    collect_sec_filings,
    load_monthly_summary,
    sort_sec_filings,
)
from src.output.pm_view import build_pm_view
from src.output.schema import SCHEMA_VERSION
from src.output.sharded_export import write_sharded_outputs
from src.output.direction_alignment import write_direction_alignment_output
from src.types import MarketRegime, PortfolioSummary, TickerAnalysis, TickerDecision
from src.utils.env import is_env_flag_enabled
from src.utils.fs_sync import retry_io
from src.utils.pipeline_logging import record_pipeline_event
from src.utils.weekly_summary import WeeklySummaryData

_MAX_DAYS = 90


def write_json_outputs(
    analyses: list[TickerAnalysis],
    run_date: date,
    *,
    market_overview: list[dict[str, str]] | None = None,
    output_root: Path | None = None,
    period_changes_by_ticker: dict[str, dict[str, str]] | None = None,
    portfolio_summary: PortfolioSummary | None = None,
    signal_stats: dict[str, Any] | None = None,
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    weekly_summary: WeeklySummaryData | None = None,
    market_regime: MarketRegime | None = None,
    decisions: list[TickerDecision] | None = None,
    backtest_summary: dict[str, Any] | None = None,
    monthly_summary: dict[str, Any] | None = None,
    derived_by_ticker: dict[str, dict[str, Any]] | None = None,
    price_history_rows: list[dict[str, str]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    decision_map = {d.ticker: d for d in (decisions or [])}
    emit_legacy_dashboard = is_env_flag_enabled("EMIT_LEGACY_DASHBOARD", default=False)
    weekly_summary_payload = {
        "schema_version": SCHEMA_VERSION,
        "iso_year": weekly_summary.iso_year if weekly_summary else run_date.isocalendar()[0],
        "iso_week": weekly_summary.iso_week if weekly_summary else run_date.isocalendar()[1],
        "start_date": weekly_summary.start_date if weekly_summary else "",
        "end_date": weekly_summary.end_date if weekly_summary else "",
        "trading_days": weekly_summary.trading_days if weekly_summary else 0,
        "weekly_report": weekly_summary.weekly_report if weekly_summary else {},
        "weekly_insight": weekly_summary.weekly_insight if weekly_summary else "",
    }

    latest_day, merged_days = _write_dashboard_jsons(
        data_dir / "dashboard.json",
        data_dir / "dashboard_history.json",
        analyses,
        run_date,
        market_overview or [],
        period_changes_by_ticker or {},
        portfolio_summary,
        signal_stats or {},
        macro_context or {},
        portfolio_risk or {},
        weekly_summary=weekly_summary,
        market_regime=market_regime,
        decision_map=decision_map,
        derived_by_ticker=derived_by_ticker,
        price_history_rows=price_history_rows,
        emit_legacy_dashboard=emit_legacy_dashboard,
        weekly_summary_payload=weekly_summary_payload,
    )
    _write_price_history_exports(
        data_dir / "price_history.json",
        data_dir / "price_history.csv",
        price_history_rows,
    )
    backtest_payload = (
        backtest_summary
        if backtest_summary is not None
        else build_backtest_summary(data_dir / "signal_tracker.csv")
    )
    (data_dir / "backtest_summary.json").write_text(
        json.dumps(backtest_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_calibration_json(data_dir)
    _write_factor_audit_json(data_dir)
    _write_signal_quality_json(data_dir)
    _write_tuning_report_json(data_dir)
    _write_validation_warnings_json(data_dir)
    write_direction_alignment_output(output_root=root)
    monthly_payload = (
        monthly_summary
        if monthly_summary is not None
        else load_monthly_summary(run_date, output_root=root)
    )
    (data_dir / "monthly_summary.json").write_text(
        json.dumps(monthly_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    timelines = _write_ticker_timelines_json(data_dir / "ticker_timelines.json", merged_days)
    if is_env_flag_enabled("EMIT_SHARDED_DASHBOARD", default=True):
        write_sharded_outputs(
            data_dir,
            latest_day,
            merged_days,
            signal_stats=signal_stats or {},
            weekly_summary=weekly_summary_payload,
        )
    # Keep the React app's `public/output/data/*` in sync with the latest exports.
    # `data_dir` is expected to be `<repo>/output/data`, so the repo root is `data_dir.parent.parent`.
    _sync_web_public_data(data_dir, data_dir.parent.parent)
    return timelines


def _write_dashboard_jsons(
    latest_path: Path,
    history_path: Path,
    analyses: list[TickerAnalysis],
    run_date: date,
    market_overview: list[dict[str, str]],
    period_changes_by_ticker: dict[str, dict[str, str]],
    portfolio_summary: PortfolioSummary | None,
    signal_stats: dict[str, Any],
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    weekly_summary: WeeklySummaryData | None = None,
    market_regime: MarketRegime | None = None,
    decision_map: dict[str, TickerDecision] | None = None,
    derived_by_ticker: dict[str, dict[str, Any]] | None = None,
    price_history_rows: list[dict[str, str]] | None = None,
    emit_legacy_dashboard: bool = False,
    weekly_summary_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    existing_days: list[dict[str, Any]] = []
    source_path = history_path if history_path.exists() else latest_path
    if source_path.exists():
        try:
            existing = json.loads(source_path.read_text(encoding="utf-8"))
            existing_days = existing.get("days", [])
        except (json.JSONDecodeError, KeyError):
            existing_days = []

    dm = decision_map or {}
    new_day = {
        "date": run_date.isoformat(),
        "market_overview": market_overview,
        "macro_context": macro_context or {},
        "market_regime": _serialize_market_regime(market_regime),
        "portfolio_risk": portfolio_risk or {},
        "portfolio_summary": _serialize_portfolio_summary(portfolio_summary),
        "pm_view": build_pm_view(
            analyses,
            as_of=run_date.isoformat(),
            portfolio_summary=portfolio_summary,
            portfolio_risk=portfolio_risk or {},
            decision_map=dm,
        ),
        "tickers": [
            _serialize_analysis(
                a,
                period_changes_by_ticker.get(a.ticker, {"7d": "N/A", "30d": "N/A"}),
                decision=dm.get(a.ticker),
                ticker_derivations=(derived_by_ticker or {}).get(a.ticker),
            )
            for a in analyses
        ],
    }

    merged = [d for d in existing_days if d.get("date") != run_date.isoformat()]
    merged.append(new_day)
    merged.sort(key=lambda d: d.get("date", ""))
    if len(merged) > _MAX_DAYS:
        merged = merged[-_MAX_DAYS:]

    merged = _reconcile_days_with_price_history(merged, price_history_rows)
    new_day = next((day for day in merged if day.get("date") == run_date.isoformat()), new_day)

    weekly_summary_payload = weekly_summary_payload or {
        "schema_version": SCHEMA_VERSION,
        "iso_year": weekly_summary.iso_year if weekly_summary else run_date.isocalendar()[0],
        "iso_week": weekly_summary.iso_week if weekly_summary else run_date.isocalendar()[1],
        "start_date": weekly_summary.start_date if weekly_summary else "",
        "end_date": weekly_summary.end_date if weekly_summary else "",
        "trading_days": weekly_summary.trading_days if weekly_summary else 0,
        "weekly_report": weekly_summary.weekly_report if weekly_summary else {},
        "weekly_insight": weekly_summary.weekly_insight if weekly_summary else "",
    }
    latest_payload = {
        "schema_version": SCHEMA_VERSION,
        "days": [new_day],
        "signal_stats": signal_stats,
        "weekly_summary": weekly_summary_payload,
    }
    history_payload = {
        "schema_version": SCHEMA_VERSION,
        "days": merged,
        "signal_stats": signal_stats,
        "weekly_summary": weekly_summary_payload,
    }

    if emit_legacy_dashboard:
        latest_path.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif latest_path.exists():
        latest_path.unlink()
    history_path.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_day, merged


def _reconcile_days_with_price_history(
    days: list[dict[str, Any]],
    price_history_rows: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    if not price_history_rows:
        return days

    snapshot_map = {
        (str(row.get("date", "")), str(row.get("ticker", ""))): {
            "Open": row.get("open", "N/A"),
            "High": row.get("high", "N/A"),
            "Low": row.get("low", "N/A"),
            "Close": row.get("close", "N/A"),
            "Volume": row.get("volume", "N/A"),
            "Price": row.get("price", "N/A"),
            "Daily Change": row.get("daily_change", "N/A"),
        }
        for row in price_history_rows
    }

    reconciled_days: list[dict[str, Any]] = []
    for day in days:
        date_value = str(day.get("date", ""))
        tickers = day.get("tickers", [])
        if not isinstance(tickers, list):
            reconciled_days.append(day)
            continue

        updated_tickers: list[dict[str, Any]] = []
        for ticker_payload in tickers:
            if not isinstance(ticker_payload, dict):
                updated_tickers.append(ticker_payload)
                continue

            ticker = str(ticker_payload.get("ticker", ""))
            snapshot_override = snapshot_map.get((date_value, ticker))
            if not snapshot_override:
                updated_tickers.append(ticker_payload)
                continue

            data_snapshot = ticker_payload.get("data_snapshot")
            if not isinstance(data_snapshot, dict):
                data_snapshot = {}
            replacements = {
                str(old_value): str(new_value)
                for key, new_value in snapshot_override.items()
                for old_value in [data_snapshot.get(key)]
                if old_value not in (None, "", "N/A") and new_value not in (None, "", "N/A") and str(old_value) != str(new_value)
            }
            merged_snapshot = {**data_snapshot, **{k: v for k, v in snapshot_override.items() if v is not None}}
            normalized_payload = _replace_snapshot_tokens(ticker_payload, replacements)
            updated_tickers.append({**normalized_payload, "data_snapshot": merged_snapshot})

        reconciled_days.append({**day, "tickers": updated_tickers})

    return reconciled_days


def _replace_snapshot_tokens(value: Any, replacements: dict[str, str]) -> Any:
    if not replacements:
        return value
    if isinstance(value, str):
        updated = value
        for old_text, new_text in replacements.items():
            updated = updated.replace(old_text, new_text)
        return updated
    if isinstance(value, list):
        return [_replace_snapshot_tokens(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_snapshot_tokens(item, replacements) for key, item in value.items()}
    return value


def _serialize_analysis(
    analysis: TickerAnalysis,
    period_changes: dict[str, str],
    *,
    decision: TickerDecision | None = None,
    ticker_derivations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if ticker_derivations is None:
        currency = _snapshot_currency(analysis.data_snapshot)
        ticker_derivations = {
            "earnings_setup": build_earnings_setup(
                analysis.fundamentals,
                analysis.quarterly_financials,
                analysis.upcoming_events,
                currency=currency,
            ),
            "earnings_surprise_history": build_earnings_surprise_summary(analysis.quarterly_financials),
            "earnings_pattern": build_earnings_pattern(analysis.quarterly_financials),
            "sec_filing_tags": collect_sec_filing_tags(analysis.news_references),
            "sec_filings": sort_sec_filings(collect_sec_filings(analysis.news_references)),
        }
    result: dict[str, Any] = {
        "ticker": analysis.ticker,
        "name": analysis.name,
        "date": analysis.date,
        "summary": analysis.summary,
        "key_news": analysis.key_news,
        "news_references": [
            {
                "title": ref.title,
                "source": ref.source,
                "published_at": ref.published_at,
                "link": ref.link,
            }
            for ref in analysis.news_references
        ],
        "financial_highlights": analysis.financial_highlights,
        "risks_or_watchpoints": analysis.risks_or_watchpoints,
        "signal_or_takeaway": analysis.signal_or_takeaway,
        "data_snapshot": analysis.data_snapshot,
        "fundamentals": analysis.fundamentals,
        "earnings_setup": ticker_derivations["earnings_setup"],
        "earnings_surprise_history": ticker_derivations["earnings_surprise_history"],
        "earnings_pattern": ticker_derivations["earnings_pattern"],
        "price_action": analysis.price_action,
        "quarterly_financials": analysis.quarterly_financials[:4],
        "upcoming_events": analysis.upcoming_events,
        "news_tone": analysis.news_tone,
        "trade_frame": analysis.trade_frame,
        "options_summary": analysis.options_summary,
        "signal_history": getattr(analysis, "signal_history", []),
        "sector_comparison": getattr(analysis, "sector_comparison", {}),
        "peer_rank": getattr(analysis, "peer_rank", {}),
        "valuation_score": getattr(analysis, "valuation_score", {}),
        "analysis_consensus": getattr(analysis, "analysis_consensus", {}),
        "committee_analysis": _serialize_committee_analysis(getattr(analysis, "committee_analysis", {})),
        "period_changes": period_changes,
        "sec_filing_tags": ticker_derivations["sec_filing_tags"],
        "sec_filings": ticker_derivations["sec_filings"],
    }
    if decision is not None:
        result["decision"] = _serialize_decision(decision, analysis_consensus=getattr(analysis, "analysis_consensus", {}))
    return result


def _serialize_market_regime(regime: MarketRegime | None) -> dict[str, Any]:
    if regime is None:
        return {}
    return {
        "regime": regime.regime,
        "confidence": regime.confidence,
        "drivers": regime.drivers,
        "implication": regime.implication,
        "assessed_at": regime.assessed_at,
    }


def _serialize_decision(
    decision: TickerDecision,
    *,
    analysis_consensus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    consensus = analysis_consensus or {}
    status = str(consensus.get("status", "not_applicable"))
    final_consensus = getattr(decision, "final_consensus", "single")
    ensemble_agreement = "single"
    if status in {"agreed", "resolved"} or final_consensus in {"agree", "resolved"}:
        ensemble_agreement = "agree"
    elif status == "conflicted" or final_consensus == "conflict":
        ensemble_agreement = "conflict"
    result = {
        "action": decision.action,
        "conviction": decision.conviction,
        "reason": decision.reason,
        "valid_until": decision.valid_until,
        "factors": decision.factors,
        "factor_reasoning": decision.factor_reasoning,
        "ensemble_agreement": ensemble_agreement,
        "final_consensus": final_consensus,
    }
    confidence_meta = getattr(decision, "confidence_meta", {})
    if confidence_meta:
        result["raw_conviction"] = getattr(decision, "raw_conviction", decision.conviction)
        result["confidence_meta"] = confidence_meta
    return result


def _serialize_committee_analysis(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _snapshot_currency(snapshot: dict[str, str]) -> str:
    price_value = str(snapshot.get("Price", "")).strip()
    if not price_value:
        return "USD"
    parts = price_value.split()
    if len(parts) >= 2 and parts[-1].isalpha():
        return parts[-1]
    return "USD"


def _write_price_history_exports(
    json_path: Path,
    csv_path: Path,
    rows: list[dict[str, str]] | None,
) -> None:
    effective_rows = rows if rows is not None else _load_price_history_rows_from_csv(csv_path)
    json_path.write_text(json.dumps(effective_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "date",
            "ticker",
            "price",
            "daily_change",
            "market_cap",
            "trailing_pe",
            "eps",
            "52w_high",
            "52w_low",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ])
        writer.writeheader()
        writer.writerows(effective_rows)


def _load_price_history_rows_from_csv(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {key.lstrip("\ufeff") if key else "": value for key, value in row.items() if key}
            for row in reader
        ]


def _write_ticker_timelines_json(path: Path, days: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    timelines = build_ticker_timelines(days)
    path.write_text(json.dumps(timelines, ensure_ascii=False, indent=2), encoding="utf-8")
    return timelines


def _serialize_portfolio_summary(portfolio_summary: PortfolioSummary | None) -> dict[str, Any] | None:
    if portfolio_summary is None:
        return None
    return {
        "positions": [
            {
                "ticker": position.ticker,
                "shares": position.shares,
                "avg_cost": position.avg_cost,
                "currency": position.currency,
                "market_price": position.market_price,
                "market_value": position.market_value,
                "cost_basis": position.cost_basis,
                "unrealized_pnl": position.unrealized_pnl,
                "unrealized_return_pct": position.unrealized_return_pct,
            }
            for position in portfolio_summary.positions
        ],
        "total_market_value": portfolio_summary.total_market_value,
        "total_cost_basis": portfolio_summary.total_cost_basis,
        "total_unrealized_pnl": portfolio_summary.total_unrealized_pnl,
        "total_unrealized_return_pct": portfolio_summary.total_unrealized_return_pct,
    }


def _write_calibration_json(data_dir: Path) -> None:
    """Emit conviction-vs-realized-return calibration payload for Admin page."""
    from src.decision.calibration import build_calibration_payload
    from src.utils.signal_tracker import load_signal_rows

    try:
        rows = load_signal_rows(data_dir / "signal_tracker.csv")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "horizons": {
                str(horizon): build_calibration_payload(rows, horizon=horizon)
                for horizon in (1, 5, 20)
            },
        }
    except Exception as exc:  # graceful degradation — never crash the pipeline
        payload = {
            "schema_version": SCHEMA_VERSION,
            "error": str(exc),
            "horizons": {},
        }
    (data_dir / "calibration.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_factor_audit_json(data_dir: Path) -> None:
    """Emit factor collinearity + IR audit payload for Admin page."""
    from src.decision.factor_audit import build_factor_audit_payload
    from src.utils.signal_tracker import load_signal_rows

    try:
        rows = load_signal_rows(data_dir / "signal_tracker.csv")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "horizons": {
                str(horizon): build_factor_audit_payload(rows, horizon=horizon)
                for horizon in (5, 20)
            },
        }
    except Exception as exc:  # graceful degradation
        payload = {
            "schema_version": SCHEMA_VERSION,
            "error": str(exc),
            "horizons": {},
        }
    (data_dir / "factor_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_signal_quality_json(data_dir: Path) -> None:
    """Emit Phase A signal-quality metrics (IC decay, rolling IC, Kelly, turnover)."""
    from src.decision.signal_quality import build_signal_quality_payload
    from src.utils.signal_tracker import load_signal_rows

    try:
        rows = load_signal_rows(data_dir / "signal_tracker.csv")
        payload = {
            "schema_version": SCHEMA_VERSION,
            **build_signal_quality_payload(rows),
        }
    except Exception as exc:  # graceful degradation
        payload = {
            "schema_version": SCHEMA_VERSION,
            "error": str(exc),
        }
    (data_dir / "signal_quality.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_tuning_report_json(data_dir: Path) -> None:
    """Emit regime-multiplier grid search + walk-forward CV + threshold suggestions.

    Read-only advisory artifact for Admin UI — does NOT rewrite
    `decision_weights.yaml`. Operator reviews and manually promotes.
    """
    from src.decision.tune_weights import build_tuning_payload
    from src.utils.signal_tracker import load_signal_rows

    try:
        rows = load_signal_rows(data_dir / "signal_tracker.csv")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "horizons": {
                str(horizon): build_tuning_payload(rows, horizon=horizon)
                for horizon in (5, 20)
            },
        }
    except Exception as exc:  # graceful degradation
        payload = {
            "schema_version": SCHEMA_VERSION,
            "error": str(exc),
            "horizons": {},
        }
    (data_dir / "tuning_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_validation_warnings_json(data_dir: Path, *, window_days: int = 14) -> None:
    """Aggregate recent LLM validation warnings into a histogram for Admin.

    Reads the last `window_days` of pipeline summary files (cheap — one
    file per day) and emits per-day counts across the four hallucination
    categories plus the drop counter. No reliance on jsonl replay.
    """
    from datetime import date as _date, timedelta

    logs_root = Path("logs") / "pipeline"
    categories = (
        "schema_violation_count",
        "fact_warning_count",
        "consistency_warning_count",
        "hallucination_warning_count",
        "dropped_unsupported_count",
    )
    series: list[dict[str, Any]] = []
    totals: dict[str, int] = {cat: 0 for cat in categories}
    today = _date.today()

    for offset in range(window_days - 1, -1, -1):
        day = today - timedelta(days=offset)
        summary_path = logs_root / f"{day.isoformat()}.summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        quality = summary.get("analyzer_quality", {}) or {}
        day_counts = {cat: int(quality.get(cat, 0) or 0) for cat in categories}
        for cat, count in day_counts.items():
            totals[cat] += count
        series.append({
            "date": day.isoformat(),
            "batch_count": int(quality.get("batch_count", 0) or 0),
            "validated_ticker_count": int(quality.get("validated_ticker_count", 0) or 0),
            "validation_failure_count": int(quality.get("validation_failure_count", 0) or 0),
            **day_counts,
        })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "window_days": window_days,
        "generated_at": today.isoformat(),
        "categories": list(categories),
        "totals": totals,
        "series": series,
    }
    (data_dir / "validation_warnings.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sync_web_public_data(data_dir: Path, project_root: Path) -> None:
    """Copy `output/data/*` into the React `public/` and `dist/` trees.

    One failed file (typically an OneDrive / antivirus lock) must NOT prevent
    the remaining files from syncing — a silent early-exit here left the UI
    several days stale in the past. Each copy is retried on transient
    OSError and logged via `record_pipeline_event` on final failure.
    """
    web_root = project_root / "web"
    if not web_root.exists():
        record_pipeline_event(
            "output",
            "warning",
            "sync_web_public_skipped",
            reason="web_dir_missing",
            path=str(web_root),
        )
        return

    target_dirs = [
        web_root / "public" / "output" / "data",
    ]
    dist_root = web_root / "dist" / "output" / "data"
    if dist_root.parent.parent.exists():
        target_dirs.append(dist_root)

    for target_dir in target_dirs:
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            record_pipeline_event(
                "output",
                "error",
                "sync_web_public_mkdir_failed",
                target=str(target_dir),
                error=str(exc),
            )

    filenames = [
        "dashboard_history.json",
        "api_status.json",
        "api_ticker_matrix.json",
        "api_ticker_matrix.csv",
        "analysis_quality.json",
        "cost_log.json",
        "routing_outcome.json",
        "direction_alignment.json",
        "ab_test_results.json",
        "price_history.json",
        "ticker_timelines.json",
        "backtest_summary.json",
        "monthly_summary.json",
        "sectors.json",
        "factor_audit.json",
        "signal_quality.json",
        "policy_impact.json",
        "index.json",
    ]
    dashboard_json = data_dir / "dashboard.json"
    if dashboard_json.exists():
        filenames.insert(0, "dashboard.json")

    copied = 0
    failed = 0
    for filename in filenames:
        source_path = data_dir / filename
        if not source_path.exists():
            continue
        for target_dir in target_dirs:
            target_path = target_dir / filename
            try:
                retry_io(
                    lambda s=source_path, t=target_path: shutil.copy2(s, t),
                    what=f"sync {target_path}",
                )
                copied += 1
            except Exception as exc:
                failed += 1
                record_pipeline_event(
                    "output",
                    "error",
                    "sync_web_public_copy_failed",
                    file=filename,
                    target=str(target_path),
                    error=str(exc),
                )

    # NOTE: previously this block unlinked web/public/dashboard.json whenever
    # the source copy wasn't present at sync time. That caused the frontend to
    # lose dashboard.json whenever sync raced a transient rewrite (e.g. when
    # intraday_refresh or sector_scan ran between source writes). dashboard.json
    # is always a desired artifact, so we no longer delete the mirror if it
    # happens to be missing at source — a later sync will recopy it once
    # source is in place.

    source_tickers = data_dir / "tickers"
    if source_tickers.is_dir():
        for target_dir in target_dirs:
            target_tickers = target_dir / "tickers"
            try:
                if target_tickers.exists():
                    shutil.rmtree(target_tickers, ignore_errors=True)
                retry_io(
                    lambda s=source_tickers, t=target_tickers: shutil.copytree(s, t),
                    what=f"sync {target_tickers}",
                )
            except Exception as exc:
                failed += 1
                record_pipeline_event(
                    "output",
                    "error",
                    "sync_web_public_copytree_failed",
                    source=str(source_tickers),
                    target=str(target_tickers),
                    error=str(exc),
                )

    record_pipeline_event(
        "output",
        "info",
        "sync_web_public_completed",
        copied=copied,
        failed=failed,
        targets=[str(d) for d in target_dirs],
    )
