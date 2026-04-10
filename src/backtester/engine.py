from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.signal_tracker import load_signal_stats


def build_backtest_summary(csv_path: Path) -> dict[str, Any]:
    signal_stats = load_signal_stats(csv_path)
    recent = signal_stats.get("recent_signals", [])
    evaluated = [row for row in recent if str(row.get("evaluated_20d", "False")).lower() == "true"]
    if not evaluated:
        return {
            "status": "insufficient_data",
            "strategy": "bull signals held for 20 trading days; bear signals skipped",
            "signals": 0,
        }

    usable_returns: list[float] = []
    wins = 0
    cumulative = 1.0
    for row in evaluated:
        if str(row.get("signal_direction", "")) != "bull":
            continue
        try:
            value = float(str(row.get("return_20d", "N/A")).replace("%", ""))
        except ValueError:
            continue
        usable_returns.append(value)
        if value > 0:
            wins += 1
        cumulative *= 1 + (value / 100.0)

    if not usable_returns:
        return {
            "status": "insufficient_data",
            "strategy": "bull signals held for 20 trading days; bear signals skipped",
            "signals": 0,
        }

    avg_return = sum(usable_returns) / len(usable_returns)
    return {
        "status": "ok",
        "strategy": "bull signals held for 20 trading days; bear signals skipped",
        "signals": len(usable_returns),
        "win_rate": f"{(wins / len(usable_returns)) * 100:.1f}%",
        "avg_return": f"{avg_return:+.2f}%",
        "cumulative_return": f"{(cumulative - 1) * 100:+.2f}%",
        "best_return": f"{max(usable_returns):+.2f}%",
        "worst_return": f"{min(usable_returns):+.2f}%",
    }
