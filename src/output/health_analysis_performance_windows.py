"""Health checks for analysis performance window statistics."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_number_or_none,
    _is_probability_or_none,
)


def _validate_analysis_performance_window_map(
    path: Path,
    label: str,
    mapping: dict,
) -> OutputHealthIssue | None:
    for group, by_horizon in mapping.items():
        if not isinstance(group, str) or not group.strip():
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{label} keys must be non-empty strings",
            )
        if not isinstance(by_horizon, dict) or not by_horizon:
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{label} {group} must be a non-empty horizon object",
            )
        for horizon, stats in by_horizon.items():
            if not isinstance(horizon, str) or not horizon.strip():
                return OutputHealthIssue(
                    "invalid_analysis_performance",
                    str(path),
                    f"{label} {group} horizon keys must be non-empty strings",
                )
            issue = _validate_analysis_performance_window_stats(path, f"{label} {group}/{horizon}", stats)
            if issue is not None:
                return issue
    return None


def _validate_analysis_performance_window_stats(
    path: Path,
    label: str,
    stats: object,
) -> OutputHealthIssue | None:
    count_fields = ("sample_count", "completed_count", "missing_count")
    number_fields = ("avg_return", "median_return")
    rate_fields = ("win_rate", "loss_rate", "directional_win_rate")
    required = {*count_fields, *number_fields, *rate_fields, "return_distribution", "triple_barrier_outcomes"}
    if not isinstance(stats, dict) or not required.issubset(stats.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"{label} missing window stats fields",
        )
    for field in count_fields:
        if not _is_non_negative_int(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a non-negative integer for {label}",
            )
    for field in number_fields:
        if not _is_number_or_none(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number or null for {label}",
            )
    for field in rate_fields:
        if not _is_probability_or_none(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number from 0 to 1 or null for {label}",
            )

    distribution = stats.get("return_distribution")
    required_distribution = {"positive", "negative", "flat"}
    if (
        not isinstance(distribution, dict)
        or not required_distribution.issubset(distribution.keys())
        or not _is_non_negative_int_mapping(distribution)
    ):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"return_distribution must include positive/negative/flat non-negative integer counts for {label}",
        )
    if not _is_non_negative_int_mapping(stats.get("triple_barrier_outcomes")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"triple_barrier_outcomes must be an object with non-negative integer counts for {label}",
        )
    return None
