from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.utils.signal_tracker import load_signal_rows, load_signal_stats


def build_backtest_summary(csv_path: Path) -> dict[str, Any]:
    signal_stats = load_signal_stats(csv_path)
    rows = load_signal_rows(csv_path)
    evaluated = [row for row in rows if str(row.get("evaluated_20d", "False")).lower() == "true"]
    pending_rows = [
        row for row in rows
        if str(row.get("signal_direction", "")).strip() in {"bull", "bear"}
        and str(row.get("evaluated_20d", "False")).lower() != "true"
    ]
    if not evaluated:
        first_eval_date = _estimate_first_eval_date(pending_rows)
        return {
            "status": "awaiting_evaluation" if pending_rows else "insufficient_data",
            "strategy": "Evaluate bull/bear signals on a 20-trading-day horizon.",
            "signals": 0,
            "pending_signals": len(pending_rows),
            "first_eval_date": first_eval_date,
            "message": _build_pending_message(first_eval_date, len(pending_rows)),
        }

    bull_rows = [row for row in evaluated if str(row.get("signal_direction", "")) == "bull"]
    bear_rows = [row for row in evaluated if str(row.get("signal_direction", "")) == "bear"]
    bull_summary = _summarize_direction(bull_rows, direction="bull")
    bear_summary = _summarize_direction(bear_rows, direction="bear")
    combined_rows = bull_rows + bear_rows
    combined_summary = _summarize_direction(combined_rows, direction="mixed")

    if combined_summary["signals"] == 0:
        first_eval_date = _estimate_first_eval_date(pending_rows)
        return {
            "status": "awaiting_evaluation" if pending_rows else "insufficient_data",
            "strategy": "Evaluate bull/bear signals on a 20-trading-day horizon.",
            "signals": 0,
            "pending_signals": len(pending_rows),
            "first_eval_date": first_eval_date,
            "message": _build_pending_message(first_eval_date, len(pending_rows)),
        }

    return {
        "status": "ok",
        "strategy": "Evaluate bull/bear signals separately on a 20-trading-day horizon.",
        "signals": combined_summary["signals"],
        "win_rate": combined_summary["win_rate"],
        "avg_return": combined_summary["avg_return"],
        "cumulative_return": combined_summary["cumulative_return"],
        "best_return": combined_summary["best_return"],
        "worst_return": combined_summary["worst_return"],
        "bull": bull_summary,
        "bear": bear_summary,
        "equity_curve": _build_equity_curve(combined_rows),
        "ticker_rows": _build_ticker_rows(combined_rows),
        "signal_meta": {
            "meta_analysis": signal_stats.get("meta_analysis", {}),
            "summary_by_direction": signal_stats.get("summary_by_direction", {}),
        },
        "pending_signals": len(pending_rows),
        "first_eval_date": _estimate_first_eval_date(pending_rows),
    }


def _summarize_direction(rows: list[dict[str, Any]], *, direction: str) -> dict[str, Any]:
    normalized_returns: list[float] = []
    raw_returns: list[float] = []
    wins = 0
    cumulative = 1.0
    for row in rows:
        raw_return = _parse_return(row.get("return_20d", "N/A"))
        signal_direction = str(row.get("signal_direction", "")).strip()
        if raw_return is None:
            continue
        interpreted = _normalize_signal_return(signal_direction, raw_return)
        if interpreted is None:
            continue
        raw_returns.append(raw_return)
        normalized_returns.append(interpreted)
        if interpreted > 0:
            wins += 1
        cumulative *= 1 + (interpreted / 100.0)

    if not normalized_returns:
        return {
            "direction": direction,
            "signals": 0,
            "win_rate": "N/A",
            "avg_return": "N/A",
            "cumulative_return": "N/A",
            "best_return": "N/A",
            "worst_return": "N/A",
        }

    avg_return = sum(normalized_returns) / len(normalized_returns)
    return {
        "direction": direction,
        "signals": len(normalized_returns),
        "win_rate": f"{(wins / len(normalized_returns)) * 100:.1f}%",
        "avg_return": f"{avg_return:+.2f}%",
        "cumulative_return": f"{(cumulative - 1) * 100:+.2f}%",
        "best_return": f"{max(normalized_returns):+.2f}%",
        "worst_return": f"{min(normalized_returns):+.2f}%",
        "best_raw_return": f"{max(raw_returns):+.2f}%",
        "worst_raw_return": f"{min(raw_returns):+.2f}%",
    }


def _build_equity_curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    cumulative = 1.0
    for row in sorted(rows, key=lambda entry: (str(entry.get("signal_date", "")), str(entry.get("ticker", "")))):
        raw_return = _parse_return(row.get("return_20d", "N/A"))
        direction = str(row.get("signal_direction", "")).strip()
        interpreted = _normalize_signal_return(direction, raw_return) if raw_return is not None else None
        if interpreted is None:
            continue
        cumulative *= 1 + (interpreted / 100.0)
        points.append(
            {
                "date": str(row.get("signal_date", "")),
                "ticker": str(row.get("ticker", "")),
                "signal_direction": direction,
                "strategy_return": f"{interpreted:+.2f}%",
                "equity_multiple": round(cumulative, 4),
                "cumulative_return": f"{(cumulative - 1) * 100:+.2f}%",
            }
        )
    return points


def _build_ticker_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    win_counts: dict[str, int] = {}
    direction_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        direction = str(row.get("signal_direction", "")).strip()
        raw_return = _parse_return(row.get("return_20d", "N/A"))
        interpreted = _normalize_signal_return(direction, raw_return) if raw_return is not None else None
        if not ticker or interpreted is None:
            continue
        grouped.setdefault(ticker, []).append(interpreted)
        direction_counts.setdefault(ticker, {"bull": 0, "bear": 0, "neutral": 0})
        direction_counts[ticker][direction if direction in direction_counts[ticker] else "neutral"] += 1
        if interpreted > 0:
            win_counts[ticker] = win_counts.get(ticker, 0) + 1

    rows_out: list[dict[str, Any]] = []
    for ticker, returns in grouped.items():
        if not returns:
            continue
        rows_out.append(
            {
                "ticker": ticker,
                "signals": len(returns),
                "avg_return": f"{sum(returns) / len(returns):+.2f}%",
                "win_rate": f"{(win_counts.get(ticker, 0) / len(returns)) * 100:.1f}%",
                "bull_signals": direction_counts.get(ticker, {}).get("bull", 0),
                "bear_signals": direction_counts.get(ticker, {}).get("bear", 0),
                "best_return": f"{max(returns):+.2f}%",
                "worst_return": f"{min(returns):+.2f}%",
            }
        )
    rows_out.sort(key=lambda item: float(str(item["avg_return"]).replace("%", "").replace("+", "")), reverse=True)
    return rows_out


def _parse_return(raw_value: Any) -> float | None:
    try:
        return float(str(raw_value).replace("%", ""))
    except ValueError:
        return None


def _normalize_signal_return(direction: str, raw_return: float) -> float | None:
    if direction == "bull":
        return raw_return
    if direction == "bear":
        return -raw_return
    return None


def _estimate_first_eval_date(rows: list[dict[str, Any]]) -> str | None:
    signal_dates = sorted(
        signal_date
        for row in rows
        if (signal_date := _parse_date(row.get("signal_date", ""))) is not None
    )
    if not signal_dates:
        return None
    return _add_business_days(signal_dates[0], 20).isoformat()


def _build_pending_message(first_eval_date: str | None, pending_signals: int) -> str:
    if first_eval_date:
        return f"Backtest statistics begin after {first_eval_date}; pending signals: {pending_signals}."
    if pending_signals > 0:
        return f"Waiting for 20-trading-day outcomes; pending signals: {pending_signals}."
    return "No completed signals are available for backtest evaluation yet."


def _add_business_days(start: date, business_days: int) -> date:
    current = start
    remaining = max(0, business_days)
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _parse_date(raw_value: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw_value).strip())
    except ValueError:
        return None
