from __future__ import annotations

import csv
import re
from datetime import date, timedelta
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
    # Triple-barrier labels (Phase A Task 2) — additive, backward compatible.
    "barrier_label",
    "barrier_hit_day",
    "barrier_return",
    "barrier_date",
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
                "barrier_label": "pending",
                "barrier_hit_day": "",
                "barrier_return": "",
                "barrier_date": "",
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


def update_triple_barrier_labels(
    csv_path: Path,
    run_date: date,
    *,
    price_history_rows: list[dict[str, str]] | None = None,
    tp: float | None = None,
    sl: float | None = None,
    horizon: int | None = None,
) -> int:
    """Fill `barrier_label` / `barrier_hit_day` / `barrier_return` for rows
    still in `pending` state. Uses OHLC bars from `price_history_rows`.

    Returns the number of rows updated. Pending rows remain pending when
    there are not yet `horizon` future sessions *and* no barrier touched.
    """
    from src.decision.triple_barrier import (
        HORIZON_DEFAULT,
        SL_DEFAULT,
        TP_DEFAULT,
        build_ohlc_series,
        label_signal,
    )

    tp_pct = tp if tp is not None else TP_DEFAULT
    sl_pct = sl if sl is not None else SL_DEFAULT
    window = horizon if horizon is not None else HORIZON_DEFAULT

    rows = _load_rows(csv_path)
    if not rows:
        return 0

    ohlc_map = build_ohlc_series(price_history_rows or [])
    updated = 0

    for row in rows:
        label = str(row.get("barrier_label", "")).strip().lower()
        if label and label != "pending":
            continue

        ticker = str(row.get("ticker", "")).strip().upper()
        signal_date = _parse_date(row.get("signal_date", ""))
        signal_price = _parse_float(row.get("signal_price", ""))
        direction = str(row.get("signal_direction", "neutral")).strip() or "neutral"
        if not ticker or signal_date is None or signal_price is None or signal_price == 0:
            continue

        sessions = ohlc_map.get(ticker, [])
        # Only sessions strictly after the signal date, bounded by run_date.
        relevant = [s for s in sessions if signal_date < s[0] <= run_date]
        if not relevant:
            continue

        result = label_signal(
            signal_date=signal_date,
            signal_price=signal_price,
            direction=direction,
            sessions=relevant,
            tp=tp_pct,
            sl=sl_pct,
            horizon=window,
        )
        if result is None:
            continue  # still pending

        row["barrier_label"] = result["barrier_label"]
        row["barrier_hit_day"] = result["barrier_hit_day"]
        row["barrier_return"] = result["barrier_return"]
        row["barrier_date"] = result.get("barrier_date", "")
        updated += 1

    _write_rows(csv_path, rows)
    return updated


def load_signal_stats(csv_path: Path) -> dict[str, Any]:
    rows = load_signal_rows(csv_path)
    return build_signal_stats_from_rows(rows)


def load_signal_rows(csv_path: Path) -> list[dict[str, str]]:
    return _load_rows(csv_path)


def _filter_recent_signals(sorted_rows: list[dict[str, str]], days: int = 90) -> list[dict[str, str]]:
    """평가 완료 여부와 관계없이 최근 days일치 시그널을 모두 반환한다."""
    cutoff = date.today() - timedelta(days=days)
    return [
        row for row in sorted_rows
        if _parse_date(row.get("signal_date", "")) is not None
        and (_parse_date(row.get("signal_date", "")) or date.min) >= cutoff
    ]


def build_signal_stats_from_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
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
        "recent_signals": _filter_recent_signals(sorted_rows),
        "summary_by_direction": summary_by_direction,
        "meta_analysis": _build_meta_analysis(rows),
    }


def load_recent_signals(csv_path: Path, ticker: str, limit: int = 5) -> list[dict[str, str]]:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker or limit <= 0:
        return []

    rows = _load_rows(csv_path)
    matched_rows = [
        row for row in rows
        if str(row.get("ticker", "")).strip().upper() == normalized_ticker
    ]
    matched_rows.sort(key=lambda row: (row.get("signal_date", ""), row.get("ticker", "")), reverse=True)

    history: list[dict[str, str]] = []
    for row in matched_rows[:limit]:
        history.append(
            {
                "date": str(row.get("signal_date", "")).strip(),
                "direction": str(row.get("signal_direction", "neutral")).strip() or "neutral",
                "catalyst": str(row.get("catalyst_tag", "")).strip(),
                "return_5d": str(row.get("return_5d", "N/A")).strip() or "N/A",
                "note": str(row.get("trade_frame_scenario", "")).strip(),
            }
        )
    return history


def _build_meta_analysis(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Deeper signal meta-analysis: by news_tone, catalyst_tag, streaks."""
    evaluated_rows = [r for r in rows if str(r.get("evaluated_5d", "False")).lower() == "true"]
    if len(evaluated_rows) < 5:
        return {"status": "insufficient_data", "total_evaluated": len(evaluated_rows)}

    # By news_tone
    tone_stats = _group_stats(evaluated_rows, "news_tone")

    # By catalyst_tag
    catalyst_stats = _group_stats(evaluated_rows, "catalyst_tag")

    # Streak analysis
    streak = _calculate_streaks(evaluated_rows)

    # Best/worst performing tickers
    ticker_performance = _ticker_performance(evaluated_rows)

    return {
        "status": "ok",
        "total_evaluated": len(evaluated_rows),
        "by_news_tone": tone_stats,
        "by_catalyst_tag": catalyst_stats,
        "streak": streak,
        "ticker_performance": ticker_performance,
    }


def _group_stats(rows: list[dict[str, str]], group_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[float]] = {}
    directions: dict[str, list[str]] = {}
    for row in rows:
        group = str(row.get(group_key, "unknown")).strip() or "unknown"
        ret = _parse_float(row.get("return_5d", ""))
        direction = str(row.get("signal_direction", "neutral"))
        if ret is None:
            continue
        groups.setdefault(group, []).append(ret)
        directions.setdefault(group, []).append(direction)

    result: dict[str, dict[str, Any]] = {}
    for group, returns in groups.items():
        if not returns:
            continue
        dir_list = directions.get(group, [])
        wins = sum(
            1 for ret, d in zip(returns, dir_list, strict=False)
            if _is_signal_win(d, ret)
        )
        result[group] = {
            "count": len(returns),
            "avg_return": _format_percent(sum(returns) / len(returns)),
            "win_rate": _format_percent(wins / len(returns) * 100),
            "best": _format_percent(max(returns)),
            "worst": _format_percent(min(returns)),
        }
    return dict(sorted(result.items(), key=lambda x: -x[1]["count"]))


def _calculate_streaks(rows: list[dict[str, str]]) -> dict[str, Any]:
    sorted_rows = sorted(rows, key=lambda r: (r.get("signal_date", ""), r.get("ticker", "")), reverse=True)
    current_streak = 0
    current_type = ""
    max_win_streak = 0
    max_loss_streak = 0
    temp_win = 0
    temp_loss = 0

    for row in sorted_rows:
        ret = _parse_float(row.get("return_5d", ""))
        direction = str(row.get("signal_direction", "neutral"))
        if ret is None:
            continue
        is_win = _is_signal_win(direction, ret)
        if is_win:
            temp_win += 1
            max_win_streak = max(max_win_streak, temp_win)
            temp_loss = 0
        else:
            temp_loss += 1
            max_loss_streak = max(max_loss_streak, temp_loss)
            temp_win = 0

    # Current streak from most recent
    for row in sorted_rows:
        ret = _parse_float(row.get("return_5d", ""))
        direction = str(row.get("signal_direction", "neutral"))
        if ret is None:
            continue
        is_win = _is_signal_win(direction, ret)
        streak_label = "win" if is_win else "loss"
        if not current_type:
            current_type = streak_label
            current_streak = 1
        elif streak_label == current_type:
            current_streak += 1
        else:
            break

    return {
        "current_streak": current_streak,
        "current_streak_type": current_type,
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
    }


def _ticker_performance(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    ticker_returns: dict[str, list[float]] = {}
    ticker_directions: dict[str, list[str]] = {}
    for row in rows:
        ticker = str(row.get("ticker", "")).strip()
        ret = _parse_float(row.get("return_5d", ""))
        direction = str(row.get("signal_direction", "neutral"))
        if not ticker or ret is None:
            continue
        ticker_returns.setdefault(ticker, []).append(ret)
        ticker_directions.setdefault(ticker, []).append(direction)

    result: list[dict[str, Any]] = []
    for ticker, returns in ticker_returns.items():
        if not returns:
            continue
        dirs = ticker_directions.get(ticker, [])
        wins = sum(1 for r, d in zip(returns, dirs, strict=False) if _is_signal_win(d, r))
        result.append({
            "ticker": ticker,
            "signals": len(returns),
            "avg_return": _format_percent(sum(returns) / len(returns)),
            "win_rate": _format_percent(wins / len(returns) * 100),
        })

    result.sort(key=lambda x: float(x["avg_return"].replace("%", "").replace("+", "")), reverse=True)
    return result


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
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(handle):
            normalized_row: dict[str, str] = {}
            for key, value in row.items():
                if not key:
                    continue
                normalized_row[key.lstrip("\ufeff")] = str(value)
            rows.append(normalized_row)
        return rows


def _write_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = sorted(rows, key=lambda row: (row.get("signal_date", ""), row.get("ticker", "")))
    # Normalize each row to the current FIELDNAMES shape so older CSVs
    # without the triple-barrier columns can be rewritten cleanly.
    normalized_rows = [
        {name: row.get(name, "") for name in FIELDNAMES}
        for row in ordered_rows
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(normalized_rows)


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
