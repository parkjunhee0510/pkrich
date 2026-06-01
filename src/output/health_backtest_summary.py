"""Health checks for backtest summary output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_number,
    _load_json_object,
)


_BACKTEST_STATUSES = {"ok", "awaiting_evaluation", "insufficient_data"}


def _validate_backtest_summary_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "backtest_summary.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "status", "strategy", "signals"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                "missing one of schema_version/status/strategy/signals",
            ),
        )

    status = payload.get("status")
    if status not in _BACKTEST_STATUSES:
        return (
            OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                "status must be one of ok/awaiting_evaluation/insufficient_data",
            ),
        )
    if not isinstance(payload.get("strategy"), str):
        return (
            OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                "strategy must be a string",
            ),
        )
    for field in ("schema_version", "signals", "pending_signals"):
        if field in payload and not _is_non_negative_int(payload.get(field)):
            return (
                OutputHealthIssue(
                    "invalid_backtest_summary",
                    str(path),
                    f"{field} must be a non-negative integer",
                ),
            )
    for field in (
        "message",
        "win_rate",
        "avg_return",
        "cumulative_return",
        "best_return",
        "worst_return",
    ):
        if field in payload and not isinstance(payload.get(field), str):
            return (
                OutputHealthIssue(
                    "invalid_backtest_summary",
                    str(path),
                    f"{field} must be a string",
                ),
            )
    if "first_eval_date" in payload and payload.get("first_eval_date") is not None:
        if not isinstance(payload.get("first_eval_date"), str):
            return (
                OutputHealthIssue(
                    "invalid_backtest_summary",
                    str(path),
                    "first_eval_date must be a string or null",
                ),
            )

    for field in ("bull", "bear"):
        summary = payload.get(field)
        if summary is None:
            continue
        issue = _validate_backtest_direction_summary(path, field, summary)
        if issue is not None:
            return (issue,)

    equity_curve = payload.get("equity_curve")
    if equity_curve is not None:
        if not isinstance(equity_curve, list):
            return (
                OutputHealthIssue(
                    "invalid_backtest_summary",
                    str(path),
                    "equity_curve must be a list",
                ),
            )
        for index, point in enumerate(equity_curve):
            issue = _validate_backtest_equity_point(path, index, point)
            if issue is not None:
                return (issue,)

    ticker_rows = payload.get("ticker_rows")
    if ticker_rows is not None:
        if not isinstance(ticker_rows, list):
            return (
                OutputHealthIssue(
                    "invalid_backtest_summary",
                    str(path),
                    "ticker_rows must be a list",
                ),
            )
        for index, row in enumerate(ticker_rows):
            issue = _validate_backtest_ticker_row(path, index, row)
            if issue is not None:
                return (issue,)

    if "signal_meta" in payload and not isinstance(payload.get("signal_meta"), dict):
        return (
            OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                "signal_meta must be an object",
            ),
        )

    return ()


def _validate_backtest_direction_summary(path: Path, field: str, summary: object) -> OutputHealthIssue | None:
    required = {
        "direction",
        "signals",
        "win_rate",
        "avg_return",
        "cumulative_return",
        "best_return",
        "worst_return",
    }
    if not isinstance(summary, dict) or not required.issubset(summary.keys()):
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"{field} must include direction/signals/win_rate/avg_return/cumulative_return/best_return/worst_return",
        )
    if not isinstance(summary.get("direction"), str):
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"direction must be a string for {field}",
        )
    if not _is_non_negative_int(summary.get("signals")):
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"signals must be a non-negative integer for {field}",
        )
    for metric in ("win_rate", "avg_return", "cumulative_return", "best_return", "worst_return"):
        if not isinstance(summary.get(metric), str):
            return OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                f"{metric} must be a string for {field}",
            )
    return None


def _validate_backtest_equity_point(path: Path, index: int, point: object) -> OutputHealthIssue | None:
    required = {"date", "ticker", "signal_direction", "strategy_return", "equity_multiple", "cumulative_return"}
    if not isinstance(point, dict) or not required.issubset(point.keys()):
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"equity_curve item {index} missing required fields",
        )
    for field in ("date", "ticker", "signal_direction", "strategy_return", "cumulative_return"):
        if not isinstance(point.get(field), str):
            return OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                f"{field} must be a string for equity_curve item {index}",
            )
    if not _is_number(point.get("equity_multiple")):
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"equity_multiple must be a number for equity_curve item {index}",
        )
    return None


def _validate_backtest_ticker_row(path: Path, index: int, row: object) -> OutputHealthIssue | None:
    required = {
        "ticker",
        "signals",
        "avg_return",
        "win_rate",
        "bull_signals",
        "bear_signals",
        "best_return",
        "worst_return",
    }
    if not isinstance(row, dict) or not required.issubset(row.keys()):
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"ticker_rows item {index} missing required fields",
        )
    if not isinstance(row.get("ticker"), str) or not row.get("ticker", "").strip():
        return OutputHealthIssue(
            "invalid_backtest_summary",
            str(path),
            f"ticker must be a non-empty string for ticker_rows item {index}",
        )
    for field in ("signals", "bull_signals", "bear_signals"):
        if not _is_non_negative_int(row.get(field)):
            return OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                f"{field} must be a non-negative integer for ticker_rows item {index}",
            )
    for field in ("avg_return", "win_rate", "best_return", "worst_return"):
        if not isinstance(row.get(field), str):
            return OutputHealthIssue(
                "invalid_backtest_summary",
                str(path),
                f"{field} must be a string for ticker_rows item {index}",
            )
    return None
