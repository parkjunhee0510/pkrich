from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.utils.datastore import get_datastore

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


@dataclass(frozen=True)
class WeeklyMarketMove:
    label: str
    start_price: str
    end_price: str
    weekly_change: str


@dataclass(frozen=True)
class WeeklyTickerMove:
    ticker: str
    name: str
    start_price: str
    end_price: str
    weekly_change: str
    weekly_change_value: float


@dataclass(frozen=True)
class WeeklyRepeatedNews:
    summary: str
    source: str
    count: int
    tickers: list[str]


@dataclass(frozen=True)
class WeeklySummaryData:
    iso_year: int
    iso_week: int
    start_date: str
    end_date: str
    trading_days: int
    is_partial: bool
    market_moves: list[WeeklyMarketMove]
    ticker_moves: list[WeeklyTickerMove]
    top_gainers: list[WeeklyTickerMove]
    top_losers: list[WeeklyTickerMove]
    repeated_news: list[WeeklyRepeatedNews]
    action_items: list[str]


def load_weekly_summary(
    run_date: date,
    *,
    output_root: Path | None = None,
) -> WeeklySummaryData:
    root = output_root or Path("output")
    dashboard_days = _load_dashboard_days(root / "data" / "dashboard.json")
    week_days = _filter_week_days(dashboard_days, run_date)

    iso_year, iso_week, _ = run_date.isocalendar()
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = date.fromisocalendar(iso_year, iso_week, 5)

    ticker_moves = _load_weekly_ticker_moves(root, week_days, run_date)
    market_moves = _build_weekly_market_moves(week_days)
    repeated_news = _build_repeated_news(week_days)
    action_items = _build_action_items(week_days)

    top_gainers = sorted(
        [move for move in ticker_moves if move.weekly_change_value > 0],
        key=lambda item: (item.weekly_change_value, item.ticker),
        reverse=True,
    )[:3]
    top_losers = sorted(
        [move for move in ticker_moves if move.weekly_change_value < 0],
        key=lambda item: (item.weekly_change_value, item.ticker),
    )[:3]

    if week_days:
        start_date = week_days[0]["date"]
        end_date = week_days[-1]["date"]
    else:
        start_date = week_start.isoformat()
        end_date = min(run_date, week_end).isoformat()

    return WeeklySummaryData(
        iso_year=iso_year,
        iso_week=iso_week,
        start_date=start_date,
        end_date=end_date,
        trading_days=len(week_days),
        is_partial=len(week_days) < 3,
        market_moves=market_moves,
        ticker_moves=ticker_moves,
        top_gainers=top_gainers,
        top_losers=top_losers,
        repeated_news=repeated_news,
        action_items=action_items,
    )


def _load_dashboard_days(path: Path) -> list[dict]:
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    days = payload.get("days", [])
    if not isinstance(days, list):
        return []

    return sorted(
        [day for day in days if isinstance(day, dict) and isinstance(day.get("date"), str)],
        key=lambda day: day["date"],
    )


def _filter_week_days(days: list[dict], run_date: date) -> list[dict]:
    iso_year, iso_week, _ = run_date.isocalendar()
    filtered: list[dict] = []
    for day in days:
        try:
            day_date = date.fromisoformat(day["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if day_date.isocalendar()[:2] == (iso_year, iso_week):
            filtered.append(day)
    return filtered


def _load_weekly_ticker_moves(
    output_root: Path,
    week_days: list[dict],
    run_date: date,
) -> list[WeeklyTickerMove]:
    latest_day = week_days[-1] if week_days else {}
    latest_tickers = latest_day.get("tickers", [])
    name_map = {
        entry.get("ticker", ""): entry.get("name", entry.get("ticker", ""))
        for entry in latest_tickers
        if isinstance(entry, dict)
    }

    iso_year, iso_week, _ = run_date.isocalendar()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    datastore = get_datastore(output_root=output_root)
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = min(run_date, date.fromisocalendar(iso_year, iso_week, 7))
    for row in datastore.query_prices(start_date=week_start, end_date=week_end):
        try:
            row_date = date.fromisoformat(row["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if row_date.isocalendar()[:2] != (iso_year, iso_week):
            continue
        ticker = row.get("ticker", "").strip()
        if not ticker:
            continue
        grouped[ticker].append(row)

    moves: list[WeeklyTickerMove] = []
    ordered_tickers = [entry.get("ticker", "") for entry in latest_tickers if isinstance(entry, dict)]
    for ticker in ordered_tickers:
        rows = sorted(grouped.get(ticker, []), key=lambda row: row["date"])
        if not rows:
            continue
        first_row = rows[0]
        last_row = rows[-1]
        start_price = first_row.get("price", "N/A")
        end_price = last_row.get("price", "N/A")
        change_value = _percent_change(_parse_numeric(start_price), _parse_numeric(end_price))
        moves.append(
            WeeklyTickerMove(
                ticker=ticker,
                name=name_map.get(ticker, ticker),
                start_price=start_price,
                end_price=end_price,
                weekly_change=_format_percent(change_value),
                weekly_change_value=change_value,
            )
        )

    return moves


def _build_weekly_market_moves(week_days: list[dict]) -> list[WeeklyMarketMove]:
    if not week_days:
        return []

    first_entries = {
        entry.get("label", ""): entry
        for entry in week_days[0].get("market_overview", [])
        if isinstance(entry, dict) and entry.get("label")
    }
    latest_entries = [
        entry
        for entry in week_days[-1].get("market_overview", [])
        if isinstance(entry, dict) and entry.get("label")
    ]

    moves: list[WeeklyMarketMove] = []
    for entry in latest_entries:
        label = str(entry.get("label", "")).strip()
        if not label:
            continue
        first_entry = first_entries.get(label, entry)
        start_price = str(first_entry.get("price", "N/A"))
        end_price = str(entry.get("price", "N/A"))
        change_value = _percent_change(_parse_numeric(start_price), _parse_numeric(end_price))
        moves.append(
            WeeklyMarketMove(
                label=label,
                start_price=start_price,
                end_price=end_price,
                weekly_change=_format_percent(change_value),
            )
        )
    return moves


def _build_repeated_news(week_days: list[dict]) -> list[WeeklyRepeatedNews]:
    seen_per_day: set[tuple[str, str, str]] = set()
    aggregated: dict[str, dict[str, object]] = {}

    for day in week_days:
        day_date = str(day.get("date", ""))
        tickers = day.get("tickers", [])
        for entry in tickers:
            if not isinstance(entry, dict):
                continue
            ticker = str(entry.get("ticker", "")).strip()
            references = entry.get("news_references", [])
            summaries = entry.get("key_news", [])
            for index, item in enumerate(references):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                normalized_title = _normalize_text(title)
                if not normalized_title:
                    continue
                dedupe_key = (day_date, ticker, normalized_title)
                if dedupe_key in seen_per_day:
                    continue
                seen_per_day.add(dedupe_key)

                source = str(item.get("source", "")).strip() or "Unknown"
                summary = ""
                if index < len(summaries) and isinstance(summaries[index], str):
                    summary = summaries[index].strip()
                display_summary = summary if summary and _normalize_text(summary) != normalized_title else title

                existing = aggregated.setdefault(
                    normalized_title,
                    {
                        "summary": display_summary,
                        "source": source,
                        "count": 0,
                        "tickers": set(),
                    },
                )
                existing["count"] = int(existing["count"]) + 1
                cast_tickers = existing["tickers"]
                if isinstance(cast_tickers, set) and ticker:
                    cast_tickers.add(ticker)

    repeated: list[WeeklyRepeatedNews] = []
    for entry in aggregated.values():
        count = int(entry["count"])
        if count < 2:
            continue
        tickers = sorted(str(ticker) for ticker in entry["tickers"])
        repeated.append(
            WeeklyRepeatedNews(
                summary=str(entry["summary"]),
                source=str(entry["source"]),
                count=count,
                tickers=tickers,
            )
        )

    return sorted(repeated, key=lambda item: (-item.count, item.summary, ",".join(item.tickers)))[:5]


def _build_action_items(week_days: list[dict]) -> list[str]:
    if not week_days:
        return []

    latest_day = week_days[-1]
    actions: list[str] = []
    for entry in latest_day.get("tickers", []):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker", "")).strip()
        signal = str(entry.get("signal_or_takeaway", "")).strip()
        if ticker and signal:
            actions.append(f"{ticker}: {signal}")
    return actions


def _parse_numeric(value: str) -> float | None:
    match = _NUMBER_PATTERN.search(value or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _percent_change(start_value: float | None, end_value: float | None) -> float:
    if start_value is None or end_value is None or start_value == 0:
        return 0.0
    return ((end_value - start_value) / start_value) * 100


def _format_percent(value: float) -> str:
    return f"{value:+.2f}%"


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())
