"""Health checks for analysis performance artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_analysis_performance_actions import _validate_analysis_performance_action_changes
from src.output.health_analysis_performance_ai_backtest import _validate_ai_recommendation_backtest
from src.output.health_analysis_performance_factors import _validate_analysis_performance_factor_attribution
from src.output.health_analysis_performance_windows import _validate_analysis_performance_window_map
from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_number_or_none,
    _is_probability_or_none,
    _is_string_list,
    _load_json_object,
)


def _validate_analysis_performance_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "analysis_performance.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {
        "schema_version",
        "as_of",
        "summary",
        "signal_performance",
        "conviction_calibration",
        "regime_performance",
        "factor_attribution",
        "action_change_reasons",
    }
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                "missing one of schema_version/as_of/summary/signal_performance/conviction_calibration/regime_performance/factor_attribution/action_change_reasons",
            ),
        )
    if not _is_non_negative_int(payload.get("schema_version")):
        return (
            OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                "schema_version must be a non-negative integer",
            ),
        )
    if not isinstance(payload.get("as_of"), str) or not payload.get("as_of", "").strip():
        return (
            OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                "as_of must be a non-empty string",
            ),
        )

    validators = (
        _validate_analysis_performance_summary,
        _validate_analysis_performance_signal_performance,
        _validate_analysis_performance_conviction_calibration,
        _validate_analysis_performance_regime_performance,
        _validate_analysis_performance_factor_attribution,
        _validate_analysis_performance_action_changes,
        _validate_ai_recommendation_backtest,
    )
    for validator in validators:
        issue = validator(path, payload)
        if issue is not None:
            return (issue,)
    return ()


def _validate_analysis_performance_summary(path: Path, payload: dict) -> OutputHealthIssue | None:
    summary = payload.get("summary")
    required = {"sample_count", "decision_count", "completed_return_windows", "mode", "notes"}
    if not isinstance(summary, dict) or not required.issubset(summary.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "summary missing sample_count/decision_count/completed_return_windows/mode/notes",
        )
    for field in ("sample_count", "decision_count"):
        if not _is_non_negative_int(summary.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a non-negative integer for summary",
            )
    if not _is_string_list(summary.get("completed_return_windows")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "completed_return_windows must be a list of strings for summary",
        )
    if not isinstance(summary.get("mode"), str) or not summary.get("mode", "").strip():
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "mode must be a non-empty string for summary",
        )
    if not _is_string_list(summary.get("notes")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "notes must be a list of strings for summary",
        )
    return None


def _validate_analysis_performance_signal_performance(path: Path, payload: dict) -> OutputHealthIssue | None:
    signal_performance = payload.get("signal_performance")
    if not isinstance(signal_performance, dict) or not signal_performance:
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "signal_performance must be a non-empty object",
        )
    return _validate_analysis_performance_window_map(path, "signal_performance", signal_performance)


def _validate_analysis_performance_conviction_calibration(path: Path, payload: dict) -> OutputHealthIssue | None:
    calibration = payload.get("conviction_calibration")
    required = {"status", "bucket_edges", "buckets"}
    if not isinstance(calibration, dict) or not required.issubset(calibration.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "conviction_calibration missing status/bucket_edges/buckets",
        )
    if not isinstance(calibration.get("status"), str) or not calibration.get("status", "").strip():
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "status must be a non-empty string for conviction_calibration",
        )
    if not _is_string_list(calibration.get("bucket_edges")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "bucket_edges must be a list of strings for conviction_calibration",
        )
    buckets = calibration.get("buckets")
    if not isinstance(buckets, dict):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "buckets must be an object for conviction_calibration",
        )
    for bucket, stats in buckets.items():
        issue = _validate_analysis_performance_conviction_bucket(path, str(bucket), stats)
        if issue is not None:
            return issue
    return None


def _validate_analysis_performance_conviction_bucket(
    path: Path,
    bucket: str,
    stats: object,
) -> OutputHealthIssue | None:
    return_fields = ("avg_return_1d", "avg_return_5d", "avg_return_20d")
    rate_fields = ("buy_win_rate", "avoid_win_rate")
    required = {"sample_count", "action_counts", *return_fields, *rate_fields}
    if not isinstance(stats, dict) or not required.issubset(stats.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"buckets {bucket} missing calibration stats",
        )
    if not _is_non_negative_int(stats.get("sample_count")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"sample_count must be a non-negative integer for conviction bucket {bucket}",
        )
    if not _is_non_negative_int_mapping(stats.get("action_counts")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"action_counts must be an object with non-negative integer counts for conviction bucket {bucket}",
        )
    for field in return_fields:
        if not _is_number_or_none(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number or null for conviction bucket {bucket}",
            )
    for field in rate_fields:
        if not _is_probability_or_none(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number from 0 to 1 or null for conviction bucket {bucket}",
            )
    return None


def _validate_analysis_performance_regime_performance(path: Path, payload: dict) -> OutputHealthIssue | None:
    regime_performance = payload.get("regime_performance")
    if not isinstance(regime_performance, dict):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "regime_performance must be an object",
        )
    for regime, by_action in regime_performance.items():
        if not isinstance(regime, str) or not regime.strip():
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                "regime_performance keys must be non-empty strings",
            )
        if not isinstance(by_action, dict):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"regime_performance {regime} must be an action object",
            )
        issue = _validate_analysis_performance_window_map(path, f"regime_performance {regime}", by_action)
        if issue is not None:
            return issue
    return None

