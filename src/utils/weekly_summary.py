from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from src.utils.datastore import get_datastore
from src.utils.signal_tracker import load_signal_stats

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
class WeeklySectorPerformance:
    sector: str
    ticker_count: int
    average_weekly_change: str


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
    sector_performance: list[WeeklySectorPerformance]
    top_gainers: list[WeeklyTickerMove]
    top_losers: list[WeeklyTickerMove]
    repeated_news: list[WeeklyRepeatedNews]
    signal_validation_rows: list[dict[str, str]]
    signal_summary: list[str]
    action_items: list[str]
    weekly_report: dict[str, object] = field(default_factory=dict)
    weekly_insight: str = ""


def load_weekly_summary(
    run_date: date,
    *,
    output_root: Path | None = None,
    macro_context: dict[str, Any] | None = None,
    market_regime: dict[str, Any] | Any | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    decisions: list[Any] | None = None,
) -> WeeklySummaryData:
    root = output_root or Path("output")
    history_path = root / "data" / "dashboard_history.json"
    dashboard_days = _load_dashboard_days(history_path if history_path.exists() else root / "data" / "dashboard.json")
    week_days = _filter_week_days(dashboard_days, run_date)

    iso_year, iso_week, _ = run_date.isocalendar()
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = date.fromisocalendar(iso_year, iso_week, 5)

    ticker_moves = _load_weekly_ticker_moves(root, week_days, run_date)
    market_moves = _build_weekly_market_moves(week_days)
    sector_performance = _build_sector_performance(week_days, ticker_moves)
    repeated_news = _build_repeated_news(week_days)
    signal_stats = load_signal_stats(root / "data" / "signal_tracker.csv")
    signal_validation_rows = _build_signal_validation_rows(signal_stats)
    signal_summary = _build_signal_summary(signal_stats)
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
    weekly_report = _load_weekly_report(
        iso_year,
        iso_week,
        week_start.isoformat(),
        min(run_date, week_end).isoformat(),
        market_moves,
        sector_performance,
        top_gainers=top_gainers,
        top_losers=top_losers,
        repeated_news=repeated_news,
        signal_summary=signal_summary,
        action_items=action_items,
        macro_context=macro_context or {},
        market_regime=market_regime,
        portfolio_risk=portfolio_risk or {},
        decisions=decisions or [],
        week_days=week_days,
    )
    weekly_insight = str(weekly_report.get("summary", "")).strip() or _load_weekly_insight(
        iso_year,
        iso_week,
        week_start.isoformat(),
        min(run_date, week_end).isoformat(),
        market_moves,
        sector_performance,
        top_gainers=top_gainers,
        top_losers=top_losers,
        repeated_news=repeated_news,
        signal_summary=signal_summary,
        action_items=action_items,
    )

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
        sector_performance=sector_performance,
        top_gainers=top_gainers,
        top_losers=top_losers,
        repeated_news=repeated_news,
        signal_validation_rows=signal_validation_rows,
        signal_summary=signal_summary,
        action_items=action_items,
        weekly_report=weekly_report,
        weekly_insight=weekly_insight,
    )


def _load_weekly_report(
    iso_year: int,
    iso_week: int,
    start_date: str,
    end_date: str,
    market_moves: list[WeeklyMarketMove],
    sector_performance: list[WeeklySectorPerformance],
    top_gainers: list[WeeklyTickerMove],
    top_losers: list[WeeklyTickerMove],
    repeated_news: list[WeeklyRepeatedNews],
    signal_summary: list[str],
    action_items: list[str],
    *,
    macro_context: dict[str, Any],
    market_regime: dict[str, Any] | Any | None,
    portfolio_risk: dict[str, Any],
    decisions: list[Any],
    week_days: list[dict[str, Any]],
) -> dict[str, object]:
    try:
        from src.analyzer.weekly_insight import generate_weekly_report

        return generate_weekly_report(
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
            market_moves=market_moves,
            sector_performance=sector_performance,
            top_gainers=top_gainers,
            top_losers=top_losers,
            repeated_news=repeated_news,
            signal_summary=signal_summary,
            action_items=action_items,
            macro_context=macro_context,
            market_regime=market_regime,
            portfolio_risk=portfolio_risk,
            decisions=decisions,
            week_days=week_days,
        )
    except Exception:
        return {}


def _load_weekly_insight(
    iso_year: int,
    iso_week: int,
    start_date: str,
    end_date: str,
    market_moves: list[WeeklyMarketMove],
    sector_performance: list[WeeklySectorPerformance],
    top_gainers: list[WeeklyTickerMove],
    top_losers: list[WeeklyTickerMove],
    repeated_news: list[WeeklyRepeatedNews],
    signal_summary: list[str],
    action_items: list[str],
) -> str:
    try:
        from src.analyzer.weekly_insight import generate_weekly_insight

        return generate_weekly_insight(
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
            market_moves=market_moves,
            sector_performance=sector_performance,
            top_gainers=top_gainers,
            top_losers=top_losers,
            repeated_news=repeated_news,
            signal_summary=signal_summary,
            action_items=action_items,
        )
    except Exception:
        return ""


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
    sqlite_path = output_root / "data" / "price_history.sqlite"
    csv_path = output_root / "data" / "price_history.csv"
    backend = "sqlite" if sqlite_path.exists() else "csv" if csv_path.exists() else None
    datastore = get_datastore(output_root=output_root, backend=backend)
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
    single_day = len(week_days) == 1

    moves: list[WeeklyMarketMove] = []
    for entry in latest_entries:
        label = str(entry.get("label", "")).strip()
        if not label:
            continue
        first_entry = first_entries.get(label, entry)
        start_price = str(first_entry.get("price", "N/A"))
        end_price = str(entry.get("price", "N/A"))

        if single_day:
            # Only 1 day in the week: price-to-price diff would be 0.
            # Use the stored daily change field (previous close → today's close) instead.
            raw_change = str(entry.get("change", "N/A")).strip()
            pct = _parse_numeric(raw_change)
            if pct is not None and raw_change.startswith(("-", "+")):
                weekly_change = f"{pct:+.2f}%"
            elif pct is not None:
                weekly_change = f"{pct:+.2f}%"
            else:
                weekly_change = raw_change if raw_change not in ("", "N/A") else "+0.00%"
        else:
            change_value = _percent_change(_parse_numeric(start_price), _parse_numeric(end_price))
            weekly_change = _format_percent(change_value)

        moves.append(
            WeeklyMarketMove(
                label=label,
                start_price=start_price,
                end_price=end_price,
                weekly_change=weekly_change,
            )
        )
    return moves


def _build_sector_performance(
    week_days: list[dict],
    ticker_moves: list[WeeklyTickerMove],
) -> list[WeeklySectorPerformance]:
    if not week_days or not ticker_moves:
        return []

    latest_day = week_days[-1]
    sector_by_ticker: dict[str, str] = {}
    for entry in latest_day.get("tickers", []):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker", "")).strip()
        snapshot = entry.get("data_snapshot", {})
        sector = ""
        if isinstance(snapshot, dict):
            sector = str(snapshot.get("Sector", "")).strip()
        if ticker:
            sector_by_ticker[ticker] = sector or "기타"

    grouped: dict[str, list[float]] = defaultdict(list)
    for move in ticker_moves:
        grouped[sector_by_ticker.get(move.ticker, "기타")].append(move.weekly_change_value)

    performance: list[WeeklySectorPerformance] = []
    for sector, values in grouped.items():
        if not values:
            continue
        average_change = sum(values) / len(values)
        performance.append(
            WeeklySectorPerformance(
                sector=sector,
                ticker_count=len(values),
                average_weekly_change=_format_percent(average_change),
            )
        )

    return sorted(performance, key=lambda item: (_parse_numeric(item.average_weekly_change) or 0.0, item.sector), reverse=True)


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


def _build_signal_validation_rows(signal_stats: dict[str, object]) -> list[dict[str, str]]:
    recent_signals = signal_stats.get("recent_signals", [])
    if not isinstance(recent_signals, list):
        return []

    rows: list[dict[str, str]] = []
    for entry in recent_signals:
        if not isinstance(entry, dict):
            continue
        if not any(str(entry.get(key, "")).strip() not in {"", "N/A"} for key in ("return_1d", "return_5d", "return_20d")):
            continue
        rows.append({key: str(value) for key, value in entry.items() if key})
    return rows[:10]


def _build_signal_summary(signal_stats: dict[str, object]) -> list[str]:
    summary_by_direction = signal_stats.get("summary_by_direction", {})
    if not isinstance(summary_by_direction, dict):
        return []

    lines: list[str] = []
    for direction in ("bull", "bear", "neutral"):
        raw_entry = summary_by_direction.get(direction, {})
        if not isinstance(raw_entry, dict):
            continue
        evaluated_count = int(raw_entry.get("evaluated_5d", 0) or 0)
        if evaluated_count <= 0:
            continue
        lines.append(
            f"{direction} 시그널 5일 승률: {raw_entry.get('win_rate_5d', 'N/A')} (평균 {raw_entry.get('avg_return_5d', 'N/A')})"
        )
    return lines


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
