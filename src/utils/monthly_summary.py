from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def load_monthly_summary(run_date: date, *, output_root: Path | None = None) -> dict[str, Any]:
    root = output_root or Path("output")
    dashboard_path = root / "data" / "dashboard.json"
    if not dashboard_path.exists():
        return {
            "month": run_date.strftime("%Y-%m"),
            "status": "no_data",
        }

    try:
        payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"month": run_date.strftime("%Y-%m"), "status": "invalid_json"}

    days = [
        day for day in payload.get("days", [])
        if isinstance(day, dict) and str(day.get("date", "")).startswith(run_date.strftime("%Y-%m"))
    ]
    if not days:
        return {"month": run_date.strftime("%Y-%m"), "status": "no_data"}

    first_day = days[0]
    latest_day = days[-1]
    ticker_changes: dict[str, list[float]] = defaultdict(list)
    sector_changes: dict[str, list[float]] = defaultdict(list)

    for day in days:
        for ticker in day.get("tickers", []):
            if not isinstance(ticker, dict):
                continue
            change = _parse_percent(ticker.get("data_snapshot", {}).get("Daily Change", "N/A"))
            if change is None:
                continue
            ticker_symbol = str(ticker.get("ticker", "")).strip()
            sector = str(ticker.get("data_snapshot", {}).get("Sector", "") or "기타").strip()
            if ticker_symbol:
                ticker_changes[ticker_symbol].append(change)
            sector_changes[sector].append(change)

    top_tickers = sorted(
        (
            {"ticker": ticker, "avg_daily_change": _format_percent(sum(values) / len(values))}
            for ticker, values in ticker_changes.items() if values
        ),
        key=lambda item: float(str(item["avg_daily_change"]).replace("%", "").replace("+", "")),
        reverse=True,
    )[:5]
    top_sectors = sorted(
        (
            {"sector": sector, "avg_daily_change": _format_percent(sum(values) / len(values))}
            for sector, values in sector_changes.items() if values
        ),
        key=lambda item: float(str(item["avg_daily_change"]).replace("%", "").replace("+", "")),
        reverse=True,
    )[:5]

    return {
        "month": run_date.strftime("%Y-%m"),
        "status": "ok",
        "trading_days": len(days),
        "start_date": first_day.get("date", ""),
        "end_date": latest_day.get("date", ""),
        "top_tickers": top_tickers,
        "top_sectors": top_sectors,
    }


def _parse_percent(value: Any) -> float | None:
    try:
        return float(str(value).replace("%", "").replace("+", "").replace(",", ""))
    except ValueError:
        return None


def _format_percent(value: float) -> str:
    return f"{value:+.2f}%"
