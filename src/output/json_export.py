"""Export dashboard and timeline data as JSON for the React frontend."""
from __future__ import annotations

import csv
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from src.types import PortfolioSummary, TickerAnalysis
from src.utils.earnings_history import build_earnings_surprise_summary
from src.utils.earnings_setup import build_earnings_setup
from src.utils.sec_filings import collect_sec_filing_tags, collect_sec_filings, sort_sec_filings
from src.utils.ticker_timelines import build_ticker_timelines

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
) -> dict[str, list[dict[str, Any]]]:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    merged_days = _write_dashboard_json(
        data_dir / "dashboard.json",
        analyses,
        run_date,
        market_overview or [],
        period_changes_by_ticker or {},
        portfolio_summary,
        signal_stats or {},
        macro_context or {},
        portfolio_risk or {},
    )
    _write_price_history_json(data_dir / "price_history.json", data_dir / "price_history.csv")
    timelines = _write_ticker_timelines_json(data_dir / "ticker_timelines.json", merged_days)
    _sync_web_public_data(data_dir, root.parent)
    return timelines


def _write_dashboard_json(
    path: Path,
    analyses: list[TickerAnalysis],
    run_date: date,
    market_overview: list[dict[str, str]],
    period_changes_by_ticker: dict[str, dict[str, str]],
    portfolio_summary: PortfolioSummary | None,
    signal_stats: dict[str, Any],
    macro_context: dict[str, Any] | None = None,
    portfolio_risk: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    existing_days: list[dict[str, Any]] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing_days = existing.get("days", [])
        except (json.JSONDecodeError, KeyError):
            existing_days = []

    new_day = {
        "date": run_date.isoformat(),
        "market_overview": market_overview,
        "macro_context": macro_context or {},
        "portfolio_risk": portfolio_risk or {},
        "portfolio_summary": _serialize_portfolio_summary(portfolio_summary),
        "tickers": [
            _serialize_analysis(a, period_changes_by_ticker.get(a.ticker, {"7d": "N/A", "30d": "N/A"}))
            for a in analyses
        ],
    }

    merged = [d for d in existing_days if d.get("date") != run_date.isoformat()]
    merged.append(new_day)
    merged.sort(key=lambda d: d.get("date", ""))
    if len(merged) > _MAX_DAYS:
        merged = merged[-_MAX_DAYS:]

    path.write_text(
        json.dumps({"days": merged, "signal_stats": signal_stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return merged


def _serialize_analysis(analysis: TickerAnalysis, period_changes: dict[str, str]) -> dict[str, Any]:
    currency = _snapshot_currency(analysis.data_snapshot)
    return {
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
        "period_changes": period_changes,
        "sec_filing_tags": collect_sec_filing_tags(analysis.news_references),
        "sec_filings": sort_sec_filings(collect_sec_filings(analysis.news_references)),
    }


def _snapshot_currency(snapshot: dict[str, str]) -> str:
    price_value = str(snapshot.get("Price", "")).strip()
    if not price_value:
        return "USD"
    parts = price_value.split()
    if len(parts) >= 2 and parts[-1].isalpha():
        return parts[-1]
    return "USD"


def _write_price_history_json(json_path: Path, csv_path: Path) -> None:
    if not csv_path.exists():
        json_path.write_text("[]", encoding="utf-8")
        return

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _sync_web_public_data(data_dir: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists():
        return

    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("dashboard.json", "price_history.json", "ticker_timelines.json"):
        source_path = data_dir / filename
        if source_path.exists():
            shutil.copy2(source_path, target_dir / filename)
