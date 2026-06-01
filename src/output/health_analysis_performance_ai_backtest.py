"""Health checks for analysis performance AI recommendation backtest telemetry."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_number_or_none,
    _is_probability_or_none,
    _is_string_list,
)

_AI_ACTIONS = ("buy", "watch", "avoid")
_AI_HORIZONS = ("1d", "5d", "20d")
_AI_CONVICTION_HORIZONS = ("5d", "20d")
_AI_CONVICTION_BUCKETS = ("65_80", "80_100")
_AI_STATUSES = ("ok", "insufficient_data")


def _validate_ai_recommendation_backtest(path: Path, payload: dict) -> OutputHealthIssue | None:
    if "ai_recommendation_backtest" not in payload:
        return None

    backtest = payload.get("ai_recommendation_backtest")
    required = {
        "status",
        "basis",
        "horizons",
        "summary",
        "by_action",
        "conviction_buckets",
        "ticker_leaderboard",
        "notable_examples",
    }
    if not isinstance(backtest, dict) or not required.issubset(backtest.keys()):
        return _issue(
            path,
            "ai_recommendation_backtest missing status/basis/horizons/summary/by_action/conviction_buckets/ticker_leaderboard/notable_examples",
        )
    if not _is_non_empty_string(backtest.get("status")):
        return _issue(path, "status must be a non-empty string for ai_recommendation_backtest")
    if backtest.get("status") not in _AI_STATUSES:
        return _issue(path, "status must be ok or insufficient_data for ai_recommendation_backtest")
    if backtest.get("basis") != "final_action":
        return _issue(path, "basis must be final_action for ai_recommendation_backtest")
    if not _is_string_list(backtest.get("horizons")):
        return _issue(path, "horizons must be a list of strings for ai_recommendation_backtest")
    if _is_ok(backtest) and backtest.get("horizons") != list(_AI_HORIZONS):
        return _issue(path, "horizons must exactly equal 1d/5d/20d for ok ai_recommendation_backtest")

    validators = (
        _validate_summary,
        _validate_by_action,
        _validate_conviction_buckets,
        _validate_ticker_leaderboard,
        _validate_notable_examples,
    )
    for validator in validators:
        issue = validator(path, backtest)
        if issue is not None:
            return issue
    return None


def _validate_summary(path: Path, backtest: dict) -> OutputHealthIssue | None:
    summary = backtest.get("summary")
    required = {"sample_count", "completed_20d_count", "best_action", "worst_action", "notes"}
    if not isinstance(summary, dict) or not required.issubset(summary.keys()):
        return _issue(path, "summary missing sample_count/completed_20d_count/best_action/worst_action/notes")
    for field in ("sample_count", "completed_20d_count"):
        if not _is_non_negative_int(summary.get(field)):
            return _issue(path, f"{field} must be a non-negative integer for ai_recommendation_backtest summary")
    for field in ("best_action", "worst_action"):
        if not _is_string_or_none(summary.get(field)):
            return _issue(path, f"{field} must be a string or null for ai_recommendation_backtest summary")
    if not _is_string_list(summary.get("notes")):
        return _issue(path, "notes must be a list of strings for ai_recommendation_backtest summary")
    return None


def _validate_by_action(path: Path, backtest: dict) -> OutputHealthIssue | None:
    by_action = backtest.get("by_action")
    if not isinstance(by_action, dict):
        return _issue(path, "by_action must be an object for ai_recommendation_backtest")
    if _is_ok(backtest) and set(by_action.keys()) != set(_AI_ACTIONS):
        return _issue(path, "by_action must contain buy/watch/avoid for ok ai_recommendation_backtest")
    return _validate_action_window_map(
        path,
        "by_action",
        by_action,
        required_horizons=_AI_HORIZONS if _is_ok(backtest) else None,
    )


def _validate_conviction_buckets(path: Path, backtest: dict) -> OutputHealthIssue | None:
    buckets = backtest.get("conviction_buckets")
    if not isinstance(buckets, dict):
        return _issue(path, "conviction_buckets must be an object for ai_recommendation_backtest")
    for bucket, stats in buckets.items():
        if not _is_non_empty_string(bucket):
            return _issue(path, "conviction_buckets keys must be non-empty strings for ai_recommendation_backtest")
        if not isinstance(stats, dict):
            return _issue(path, f"conviction_buckets {bucket} must be an object")
        required = {"sample_count", "action_counts", "by_action"}
        if not required.issubset(stats.keys()):
            return _issue(path, f"conviction_buckets {bucket} missing sample_count/action_counts/by_action")
        if not _is_non_negative_int(stats.get("sample_count")):
            return _issue(path, f"sample_count must be a non-negative integer for conviction_buckets {bucket}")
        if not _is_non_negative_int_mapping(stats.get("action_counts")):
            return _issue(
                path,
                f"action_counts must be an object with non-negative integer counts for conviction_buckets {bucket}",
            )
        by_action = stats.get("by_action")
        if not isinstance(by_action, dict):
            return _issue(path, f"by_action must be an object for conviction_buckets {bucket}")
        required_horizons = None
        if _is_ok(backtest) and bucket in _AI_CONVICTION_BUCKETS:
            if set(by_action.keys()) != set(_AI_ACTIONS):
                return _issue(path, f"by_action must contain buy/watch/avoid for conviction_buckets {bucket}")
            required_horizons = _AI_CONVICTION_HORIZONS
        issue = _validate_action_window_map(
            path,
            f"conviction_buckets {bucket} by_action",
            by_action,
            required_horizons=required_horizons,
        )
        if issue is not None:
            return issue
    return None


def _validate_action_window_map(
    path: Path,
    label: str,
    mapping: dict,
    *,
    required_horizons: tuple[str, ...] | None = None,
) -> OutputHealthIssue | None:
    for action, by_horizon in mapping.items():
        if not _is_non_empty_string(action):
            return _issue(path, f"{label} keys must be non-empty strings for ai_recommendation_backtest")
        if not isinstance(by_horizon, dict):
            return _issue(path, f"{label} {action} must be a horizon object")
        if required_horizons is not None and set(by_horizon.keys()) != set(required_horizons):
            return _issue(path, f"{label} {action} must contain {'/'.join(required_horizons)} window stats")
        for horizon, stats in by_horizon.items():
            if not _is_non_empty_string(horizon):
                return _issue(path, f"{label} {action} horizon keys must be non-empty strings")
            issue = _validate_window_stats(path, f"{label} {action}/{horizon}", stats)
            if issue is not None:
                return issue
    return None


def _validate_window_stats(path: Path, label: str, stats: object) -> OutputHealthIssue | None:
    count_fields = ("sample_count", "completed_count", "missing_count")
    number_fields = ("avg_return", "median_return", "best_return", "worst_return")
    rate_fields = ("win_rate", "loss_rate")
    required = {*count_fields, *number_fields, *rate_fields}
    if not isinstance(stats, dict) or not required.issubset(stats.keys()):
        return _issue(path, f"{label} missing AI window stats fields")
    for field in count_fields:
        if not _is_non_negative_int(stats.get(field)):
            return _issue(path, f"{field} must be a non-negative integer for {label}")
    for field in number_fields:
        if not _is_number_or_none(stats.get(field)):
            return _issue(path, f"{field} must be a number or null for {label}")
    for field in rate_fields:
        if not _is_probability_or_none(stats.get(field)):
            return _issue(path, f"{field} must be a number from 0 to 1 or null for {label}")
    return None


def _validate_ticker_leaderboard(path: Path, backtest: dict) -> OutputHealthIssue | None:
    leaderboard = backtest.get("ticker_leaderboard")
    if not isinstance(leaderboard, list):
        return _issue(path, "ticker_leaderboard must be a list for ai_recommendation_backtest")
    for index, row in enumerate(leaderboard):
        if not isinstance(row, dict):
            return _issue(path, f"ticker_leaderboard row {index} must be an object")
        if not _is_non_empty_string(row.get("ticker")):
            return _issue(path, f"ticker must be a non-empty string for ticker_leaderboard row {index}")
        for field in (
            "signals",
            "buy_signals",
            "watch_signals",
            "avoid_signals",
            "completed_5d_count",
            "completed_20d_count",
        ):
            value = row.get(field)
            if field == "watch_signals" and value is None:
                continue
            if not _is_non_negative_int(value):
                return _issue(path, f"{field} must be a non-negative integer for ticker_leaderboard row {index}")
        for field in ("avg_return_5d", "avg_return_20d"):
            if not _is_number_or_none(row.get(field)):
                return _issue(path, f"{field} must be a number or null for ticker_leaderboard row {index}")
        for field in ("win_rate_5d", "win_rate_20d"):
            if not _is_probability_or_none(row.get(field)):
                return _issue(path, f"{field} must be a number from 0 to 1 or null for ticker_leaderboard row {index}")
    return None


def _validate_notable_examples(path: Path, backtest: dict) -> OutputHealthIssue | None:
    examples = backtest.get("notable_examples")
    if not isinstance(examples, dict) or not {"best", "worst"}.issubset(examples.keys()):
        return _issue(path, "notable_examples must be an object with best and worst lists")
    for field in ("best", "worst"):
        rows = examples.get(field)
        if not isinstance(rows, list):
            return _issue(path, f"notable_examples {field} must be a list")
        for index, row in enumerate(rows):
            issue = _validate_notable_example_row(path, field, index, row)
            if issue is not None:
                return issue
    return None


def _validate_notable_example_row(
    path: Path,
    field: str,
    index: int,
    row: object,
) -> OutputHealthIssue | None:
    if not isinstance(row, dict):
        return _issue(path, f"notable_examples {field} row {index} must be an object")
    for name in ("signal_date", "ticker", "action"):
        if not _is_non_empty_string(row.get(name)):
            return _issue(path, f"{name} must be a non-empty string for notable_examples {field} row {index}")
    for name in ("catalyst_tag", "regime"):
        if not isinstance(row.get(name), str):
            return _issue(path, f"{name} must be a string for notable_examples {field} row {index}")
    for name in ("conviction", "return_5d", "return_20d"):
        if not _is_number_or_none(row.get(name)):
            return _issue(path, f"{name} must be a number or null for notable_examples {field} row {index}")
    return None


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_or_none(value: object) -> bool:
    return value is None or isinstance(value, str)


def _is_ok(backtest: dict) -> bool:
    return backtest.get("status") == "ok"


def _issue(path: Path, detail: str) -> OutputHealthIssue:
    return OutputHealthIssue("invalid_analysis_performance", str(path), detail)
