"""Sharded dashboard output — per-ticker files + lightweight index.

Schema (v1):
- ``data/index.json`` — eager-loaded dashboard summary. Contains market-wide
  context (regime, overview, macro, weekly, portfolio, signal_stats) and a
  compact ticker-summary list used by the main dashboard view.
- ``data/tickers/<TICKER>/latest.json`` — full per-ticker payload for the
  latest run (lazy-loaded on detail view).
- ``data/tickers/<TICKER>/history.json`` — rolling per-ticker history
  (lazy-loaded on detail view).

The legacy ``dashboard.json`` / ``dashboard_history.json`` remain the source
of truth during rollout; this module is additive.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.output.schema import SCHEMA_VERSION

_SUMMARY_KEYS = (
    "ticker",
    "name",
    "date",
    "summary",
    "signal_or_takeaway",
    "data_snapshot",
    "fundamentals",
    "earnings_setup",
    "earnings_pattern",
    "price_action",
    "upcoming_events",
    "news_tone",
    "news_references",
    "trade_frame",
    "options_summary",
    "period_changes",
    "sec_filing_tags",
    "sec_filings",
    "valuation_score",
    "peer_rank",
    "decision",
    "analysis_consensus",
    "committee_analysis",
)


def write_sharded_outputs(
    data_dir: Path,
    latest_day: dict[str, Any],
    merged_days: list[dict[str, Any]],
    *,
    signal_stats: dict[str, Any] | None = None,
    weekly_summary: dict[str, Any] | None = None,
) -> None:
    tickers_dir = data_dir / "tickers"
    tickers_dir.mkdir(parents=True, exist_ok=True)

    _write_index(data_dir / "index.json", latest_day, signal_stats=signal_stats, weekly_summary=weekly_summary)
    _write_per_ticker_files(tickers_dir, latest_day, merged_days)


def _write_index(
    path: Path,
    latest_day: dict[str, Any],
    *,
    signal_stats: dict[str, Any] | None = None,
    weekly_summary: dict[str, Any] | None = None,
) -> None:
    tickers_summary = [
        {key: payload.get(key) for key in _SUMMARY_KEYS if key in payload}
        for payload in latest_day.get("tickers", [])
    ]
    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "date": latest_day.get("date", ""),
        "market_overview": latest_day.get("market_overview", []),
        "macro_context": latest_day.get("macro_context", {}),
        "market_regime": latest_day.get("market_regime", {}),
        "pm_view": latest_day.get("pm_view", {}),
        "portfolio_summary": latest_day.get("portfolio_summary"),
        "portfolio_risk": latest_day.get("portfolio_risk", {}),
        "signal_stats": signal_stats or {},
        "weekly_summary": weekly_summary or {},
        "tickers": tickers_summary,
    }
    path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_per_ticker_files(
    tickers_dir: Path,
    latest_day: dict[str, Any],
    merged_days: list[dict[str, Any]],
) -> None:
    run_date = str(latest_day.get("date", ""))

    for ticker_payload in latest_day.get("tickers", []):
        ticker = str(ticker_payload.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        ticker_dir = tickers_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        latest_file = {
            "schema_version": SCHEMA_VERSION,
            "date": run_date,
            "ticker": ticker,
            "payload": ticker_payload,
        }
        (ticker_dir / "latest.json").write_text(
            json.dumps(latest_file, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    history_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for day in merged_days:
        day_date = str(day.get("date", ""))
        for ticker_payload in day.get("tickers", []):
            ticker = str(ticker_payload.get("ticker", "")).strip().upper()
            if not ticker:
                continue
            history_by_ticker.setdefault(ticker, []).append(
                {"date": day_date, **ticker_payload}
            )

    for ticker, days in history_by_ticker.items():
        ticker_dir = tickers_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        days.sort(key=lambda d: str(d.get("date", "")))
        history_file = {
            "schema_version": SCHEMA_VERSION,
            "ticker": ticker,
            "days": days,
        }
        (ticker_dir / "history.json").write_text(
            json.dumps(history_file, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    active_tickers = {
        str(payload.get("ticker", "")).strip().upper()
        for payload in latest_day.get("tickers", [])
        if str(payload.get("ticker", "")).strip()
    }
    for ticker_dir in tickers_dir.iterdir():
        if not ticker_dir.is_dir():
            continue
        if ticker_dir.name.upper() in active_tickers:
            continue
        shutil.rmtree(ticker_dir, ignore_errors=True)
