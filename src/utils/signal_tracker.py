from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path
from typing import Any

from src.types import TickerAnalysis
from src.utils.sec_filings import collect_sec_filings

FIELDNAMES = [
    "signal_date",
    "ticker",
    "signal_type",
    "signal_direction",
    "signal_price",
    "catalyst_tag",
    "news_tone",
    "trade_frame_scenario",
    "return_1d",
    "return_5d",
    "return_20d",
    "evaluated_1d",
    "evaluated_5d",
    "evaluated_20d",
]
_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_BULLISH_TERMS = ("상승", "강세", "반등", "회복", "돌파", "bull")
_BEARISH_TERMS = ("하락", "약세", "조정", "이탈", "리스크", "bear")


def record_signals(
    analyses: list[TickerAnalysis],
    run_date: date,
    price_lookup: dict[str, float],
    csv_path: Path,
) -> None:
    rows = _load_rows(csv_path)
    replacement_keys = {(run_date.isoformat(), analysis.ticker) for analysis in analyses}
    retained = [row for row in rows if (row.get("signal_date"), row.get("ticker")) not in replacement_keys]

    for analysis in analyses:
        signal_price = price_lookup.get(analysis.ticker)
        if signal_price is None:
            continue
        filings = collect_sec_filings(analysis.news_references)
        primary_filing = filings[0] if filings else {}
        retained.append(
            {
                "signal_date": run_date.isoformat(),
                "ticker": analysis.ticker,
                "signal_type": str(primary_filing.get("form_type", "") or "takeaway"),
                "signal_direction": _classify_signal_direction(analysis),
                "signal_price": f"{signal_price:.2f}",
                "catalyst_tag": str(primary_filing.get("tag", "") or "일반 이슈"),
                "news_tone": str(analysis.news_tone.get("label", "neutral")),
                "trade_frame_scenario": str(analysis.trade_frame.get("base_scenario", "") or analysis.signal_or_takeaway),
                "return_1d": row_default(),
                "return_5d": row_default(),
                "return_20d": row_default(),
                "evaluated_1d": "False",
                "evaluated_5d": "False",
                "evaluated_20d": "False",
            }
        )

    _write_rows(csv_path, retained)


def update_signal_returns(
    csv_path: Path,
    run_date: date,
    price_lookup: dict[str, float],
    *,
    price_history_rows: list[dict[str, str]] | None = None,
) -> int:
    rows = _load_rows(csv_path)
    if not rows:
        return 0

    price_series = _build_price_series(price_history_rows or [], run_date, price_lookup)
    updated_row_keys: set[tuple[str, str]] = set()

    for row in rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        signal_date = _parse_date(row.get("signal_date", ""))
        signal_price = _parse_float(row.get("signal_price", ""))
        if not ticker or signal_date is None or signal_price is None or signal_price == 0:
            continue

        future_sessions = _future_trading_sessions(price_series.get(ticker, []), signal_date, run_date)
        if not future_sessions:
            continue

        for horizon in (1, 5, 20):
            evaluated_key = f"evaluated_{horizon}d"
            return_key = f"return_{horizon}d"
            if str(row.get(evaluated_key, "False")).lower() == "true":
                continue
            if len(future_sessions) < horizon:
                continue
            _, horizon_price = future_sessions[horizon - 1]
            row[return_key] = _format_percent(((horizon_price - signal_price) / signal_price) * 100)
            row[evaluated_key] = "True"
            updated_row_keys.add((row.get("signal_date", ""), ticker))

    _write_rows(csv_path, rows)
    return len(updated_row_keys)


def load_signal_stats(csv_path: Path) -> dict[str, Any]:
    rows = _load_rows(csv_path)
    sorted_rows = sorted(rows, key=lambda row: (row.get("signal_date", ""), row.get("ticker", "")), reverse=True)
    summary_by_direction: dict[str, dict[str, Any]] = {}
    for direction in ("bull", "bear", "neutral"):
        direction_rows = [row for row in rows if row.get("signal_direction") == direction]
        evaluated_rows = [row for row in direction_rows if str(row.get("evaluated_5d", "False")).lower() == "true"]
        evaluated_returns = [_parse_float(row.get("return_5d", "")) for row in evaluated_rows]
        usable_returns = [value for value in evaluated_returns if value is not None]
        win_count = 0
        for row, value in zip(evaluated_rows, evaluated_returns, strict=False):
            if value is None:
                continue
            if _is_signal_win(direction, value):
                win_count += 1
        avg_return = sum(usable_returns) / len(usable_returns) if usable_returns else None
        win_rate = (win_count / len(usable_returns) * 100) if usable_returns else None
        summary_by_direction[direction] = {
            "count": len(direction_rows),
            "evaluated_5d": len(usable_returns),
            "win_rate_5d": _format_percent(win_rate) if win_rate is not None else "N/A",
            "avg_return_5d": _format_percent(avg_return) if avg_return is not None else "N/A",
        }

    return {
        "recent_signals": sorted_rows[:30],
        "summary_by_direction": summary_by_direction,
    }


def row_default() -> str:
    return "N/A"


def _classify_signal_direction(analysis: TickerAnalysis) -> str:
    signal_text = analysis.signal_or_takeaway.lower()
    text = f"{analysis.signal_or_takeaway} {analysis.trade_frame.get('base_scenario', '')}".lower()
    if any(term in signal_text for term in _BEARISH_TERMS):
        return "bear"
    if any(term in signal_text for term in _BULLISH_TERMS):
        return "bull"
    if any(term in text for term in _BULLISH_TERMS):
        return "bull"
    if any(term in text for term in _BEARISH_TERMS):
        return "bear"
    tone_label = str(analysis.news_tone.get("label", "neutral"))
    if tone_label in {"bullish", "bearish"}:
        return "bull" if tone_label == "bullish" else "bear"
    return "neutral"


def _is_signal_win(direction: str, return_value: float) -> bool:
    if direction == "bull":
        return return_value > 0
    if direction == "bear":
        return return_value < 0
    return abs(return_value) <= 1.0


def _build_price_series(
    price_history_rows: list[dict[str, str]],
    run_date: date,
    current_price_lookup: dict[str, float],
) -> dict[str, list[tuple[date, float]]]:
    series_map: dict[str, dict[date, float]] = {}

    for row in price_history_rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        row_date = _parse_date(row.get("date", ""))
        price = _parse_float(row.get("price", ""))
        if not ticker or row_date is None or price is None:
            continue
        series_map.setdefault(ticker, {})[row_date] = price

    for ticker, price in current_price_lookup.items():
        if price is None:
            continue
        series_map.setdefault(ticker.upper(), {})[run_date] = price

    return {
        ticker: sorted(price_by_date.items(), key=lambda item: item[0])
        for ticker, price_by_date in series_map.items()
    }


def _future_trading_sessions(
    sessions: list[tuple[date, float]],
    signal_date: date,
    run_date: date,
) -> list[tuple[date, float]]:
    return [
        (session_date, session_price)
        for session_date, session_price in sessions
        if signal_date < session_date <= run_date
    ]


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: str(value) for key, value in row.items() if key} for row in csv.DictReader(handle)]


def _write_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = sorted(rows, key=lambda row: (row.get("signal_date", ""), row.get("ticker", "")))
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(ordered_rows)


def _parse_date(raw_value: str) -> date | None:
    try:
        return date.fromisoformat(str(raw_value).strip())
    except ValueError:
        return None


def _parse_float(raw_value: object) -> float | None:
    text = str(raw_value).strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _format_percent(value: float) -> str:
    return f"{value:+.2f}%"
