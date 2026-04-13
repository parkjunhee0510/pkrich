"""Export dashboard and timeline data as JSON for the React frontend."""
from __future__ import annotations

import csv
import json
import sqlite3
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from src.backtester.engine import build_backtest_summary
from src.types import MarketRegime, PortfolioSummary, TickerAnalysis, TickerDecision
from src.utils.earnings_history import build_earnings_surprise_summary
from src.utils.earnings_setup import build_earnings_setup
from src.utils.monthly_summary import load_monthly_summary
from src.utils.sec_filings import collect_sec_filing_tags, collect_sec_filings, sort_sec_filings
from src.utils.ticker_timelines import build_ticker_timelines
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
) -> dict[str, list[dict[str, Any]]]:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    decision_map = {d.ticker: d for d in (decisions or [])}
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
    )
    _write_price_history_exports(
        data_dir / "price_history.json",
        data_dir / "price_history.csv",
        data_dir / "price_history.sqlite",
    )
    _write_backtest_summary_json(data_dir / "backtest_summary.json", data_dir / "signal_tracker.csv")
    _write_monthly_summary_json(data_dir / "monthly_summary.json", run_date, root)
    timelines = _write_ticker_timelines_json(data_dir / "ticker_timelines.json", merged_days)
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
        "tickers": [
            _serialize_analysis(
                a,
                period_changes_by_ticker.get(a.ticker, {"7d": "N/A", "30d": "N/A"}),
                decision=dm.get(a.ticker),
            )
            for a in analyses
        ],
    }

    merged = [d for d in existing_days if d.get("date") != run_date.isoformat()]
    merged.append(new_day)
    merged.sort(key=lambda d: d.get("date", ""))
    if len(merged) > _MAX_DAYS:
        merged = merged[-_MAX_DAYS:]

    merged = _reconcile_days_with_price_history(merged, latest_path.parent)
    new_day = next((day for day in merged if day.get("date") == run_date.isoformat()), new_day)

    weekly_summary_payload = {
        "iso_year": weekly_summary.iso_year if weekly_summary else run_date.isocalendar()[0],
        "iso_week": weekly_summary.iso_week if weekly_summary else run_date.isocalendar()[1],
        "start_date": weekly_summary.start_date if weekly_summary else "",
        "end_date": weekly_summary.end_date if weekly_summary else "",
        "trading_days": weekly_summary.trading_days if weekly_summary else 0,
        "weekly_insight": weekly_summary.weekly_insight if weekly_summary else "",
    }
    latest_payload = {
        "days": [new_day],
        "signal_stats": signal_stats,
        "weekly_summary": weekly_summary_payload,
    }
    history_payload = {
        "days": merged,
        "signal_stats": signal_stats,
        "weekly_summary": weekly_summary_payload,
    }

    latest_path.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    history_path.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_day, merged


def _reconcile_days_with_price_history(days: list[dict[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    sqlite_path = data_dir / "price_history.sqlite"
    if not sqlite_path.exists():
        return days

    try:
        with sqlite3.connect(sqlite_path) as connection:
            cursor = connection.cursor()
            rows = cursor.execute(
                "select date, ticker, open, high, low, close, volume, price, daily_change from prices"
            ).fetchall()
    except sqlite3.Error:
        return days

    snapshot_map = {
        (str(row[0]), str(row[1])): {
            "Open": row[2],
            "High": row[3],
            "Low": row[4],
            "Close": row[5],
            "Volume": row[6],
            "Price": row[7],
            "Daily Change": row[8],
        }
        for row in rows
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
) -> dict[str, Any]:
    currency = _snapshot_currency(analysis.data_snapshot)
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
        "earnings_setup": build_earnings_setup(
            analysis.fundamentals,
            analysis.quarterly_financials,
            analysis.upcoming_events,
            currency=currency,
        ),
        "earnings_surprise_history": build_earnings_surprise_summary(analysis.quarterly_financials),
        "price_action": analysis.price_action,
        "quarterly_financials": analysis.quarterly_financials[:4],
        "upcoming_events": analysis.upcoming_events,
        "news_tone": analysis.news_tone,
        "trade_frame": analysis.trade_frame,
        "options_summary": analysis.options_summary,
        "signal_history": getattr(analysis, "signal_history", []),
        "sector_comparison": getattr(analysis, "sector_comparison", {}),
        "valuation_score": getattr(analysis, "valuation_score", {}),
        "period_changes": period_changes,
        "sec_filing_tags": collect_sec_filing_tags(analysis.news_references),
        "sec_filings": sort_sec_filings(collect_sec_filings(analysis.news_references)),
    }
    if decision is not None:
        result["decision"] = _serialize_decision(decision)
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


def _serialize_decision(decision: TickerDecision) -> dict[str, Any]:
    return {
        "action": decision.action,
        "conviction": decision.conviction,
        "reason": decision.reason,
        "valid_until": decision.valid_until,
        "factors": decision.factors,
    }


def _snapshot_currency(snapshot: dict[str, str]) -> str:
    price_value = str(snapshot.get("Price", "")).strip()
    if not price_value:
        return "USD"
    parts = price_value.split()
    if len(parts) >= 2 and parts[-1].isalpha():
        return parts[-1]
    return "USD"


def _write_price_history_exports(json_path: Path, csv_path: Path, sqlite_path: Path) -> None:
    rows = _load_price_history_rows(sqlite_path, csv_path)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

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
        writer.writerows(rows)


def _load_price_history_rows(sqlite_path: Path, csv_path: Path) -> list[dict[str, str]]:
    if sqlite_path.exists():
        try:
            with sqlite3.connect(sqlite_path) as connection:
                cursor = connection.execute(
                    """
                    SELECT
                        date,
                        ticker,
                        price,
                        daily_change,
                        market_cap,
                        trailing_pe,
                        eps,
                        high_52w,
                        low_52w,
                        open,
                        high,
                        low,
                        close,
                        volume
                    FROM prices
                    ORDER BY date, ticker
                    """
                )
                return [
                    {
                        "date": str(row[0]),
                        "ticker": str(row[1]),
                        "price": str(row[2]),
                        "daily_change": str(row[3]),
                        "market_cap": str(row[4]),
                        "trailing_pe": str(row[5]),
                        "eps": str(row[6]),
                        "52w_high": str(row[7]),
                        "52w_low": str(row[8]),
                        "open": str(row[9]),
                        "high": str(row[10]),
                        "low": str(row[11]),
                        "close": str(row[12]),
                        "volume": str(row[13]),
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error:
            pass

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


def _write_backtest_summary_json(path: Path, signal_csv_path: Path) -> None:
    payload = build_backtest_summary(signal_csv_path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_monthly_summary_json(path: Path, run_date: date, output_root: Path) -> None:
    payload = load_monthly_summary(run_date, output_root=output_root)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _sync_web_public_data(data_dir: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists():
        return

    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in (
        "dashboard.json",
        "dashboard_history.json",
        "api_status.json",
        "api_ticker_matrix.json",
        "api_ticker_matrix.csv",
        "price_history.json",
        "ticker_timelines.json",
        "backtest_summary.json",
        "monthly_summary.json",
    ):
        source_path = data_dir / filename
        if source_path.exists():
            shutil.copy2(source_path, target_dir / filename)
