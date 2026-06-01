"""Health checks for signal-quality IC panels."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_correlation,
    _is_correlation_or_none,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
)


def _validate_signal_ic_decay(path: Path, payload: dict) -> OutputHealthIssue | None:
    panel = payload.get("ic_decay")
    if not isinstance(panel, dict):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "ic_decay must be an object",
        )
    if not isinstance(panel.get("status"), str):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "ic_decay status must be a string",
        )
    if not _is_non_negative_int_mapping(panel.get("sample_sizes")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "sample_sizes must be an object with non-negative integer counts for ic_decay",
        )
    factors = panel.get("factors")
    if not isinstance(factors, list):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "ic_decay factors must be a list",
        )
    for index, factor in enumerate(factors):
        issue = _validate_signal_ic_factor(path, "ic_decay", index, factor)
        if issue is not None:
            return issue
    return None


def _validate_signal_ic_factor(path: Path, panel_name: str, index: int, factor: object) -> OutputHealthIssue | None:
    required = {"factor", "ic", "n", "monotonic_decay"}
    if not isinstance(factor, dict) or not required.issubset(factor.keys()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"{panel_name} factors item {index} missing factor/ic/n/monotonic_decay",
        )
    if not isinstance(factor.get("factor"), str) or not factor.get("factor", "").strip():
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"factor must be a non-empty string for {panel_name} factors item {index}",
        )
    ic = factor.get("ic")
    if not isinstance(ic, dict) or not all(isinstance(key, str) and _is_correlation_or_none(value) for key, value in ic.items()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"ic must be an object with correlation or null values for {panel_name} factors item {index}",
        )
    if not _is_non_negative_int_mapping(factor.get("n")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"n must be an object with non-negative integer counts for {panel_name} factors item {index}",
        )
    if not isinstance(factor.get("monotonic_decay"), bool):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"monotonic_decay must be a boolean for {panel_name} factors item {index}",
        )
    return None


def _validate_signal_rolling_ic(path: Path, payload: dict) -> OutputHealthIssue | None:
    panel = payload.get("rolling_ic")
    if not isinstance(panel, dict):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "rolling_ic must be an object",
        )
    if not isinstance(panel.get("status"), str):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "rolling_ic status must be a string",
        )
    for field in ("sample_size", "horizon", "window_days", "step_days"):
        if field in panel and not _is_non_negative_int(panel.get(field)):
            return OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                f"{field} must be a non-negative integer for rolling_ic",
            )
    factors = panel.get("factors")
    if not isinstance(factors, list):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "rolling_ic factors must be a list",
        )
    for index, factor in enumerate(factors):
        issue = _validate_signal_rolling_factor(path, index, factor)
        if issue is not None:
            return issue
    return None


def _validate_signal_rolling_factor(path: Path, index: int, factor: object) -> OutputHealthIssue | None:
    required = {"factor", "series", "latest_ic", "lifetime_avg_ic", "fatigue"}
    if not isinstance(factor, dict) or not required.issubset(factor.keys()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"rolling_ic factors item {index} missing factor/series/latest_ic/lifetime_avg_ic/fatigue",
        )
    if not isinstance(factor.get("factor"), str) or not factor.get("factor", "").strip():
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"factor must be a non-empty string for rolling_ic factors item {index}",
        )
    for field in ("latest_ic", "lifetime_avg_ic"):
        if not _is_correlation(factor.get(field)):
            return OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                f"{field} must be a number from -1 to 1 for rolling_ic factors item {index}",
            )
    if not isinstance(factor.get("fatigue"), bool):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"fatigue must be a boolean for rolling_ic factors item {index}",
        )
    series = factor.get("series")
    if not isinstance(series, list):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"series must be a list for rolling_ic factors item {index}",
        )
    for point_index, point in enumerate(series):
        issue = _validate_signal_rolling_point(path, index, point_index, point)
        if issue is not None:
            return issue
    return None


def _validate_signal_rolling_point(path: Path, factor_index: int, point_index: int, point: object) -> OutputHealthIssue | None:
    required = {"window_end", "ic", "n"}
    if not isinstance(point, dict) or not required.issubset(point.keys()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"series item {point_index} missing window_end/ic/n for rolling_ic factors item {factor_index}",
        )
    if not isinstance(point.get("window_end"), str) or not point.get("window_end", "").strip():
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"window_end must be a non-empty string for rolling_ic series item {point_index}",
        )
    if not _is_correlation(point.get("ic")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"ic must be a number from -1 to 1 for rolling_ic series item {point_index}",
        )
    if not _is_non_negative_int(point.get("n")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"n must be a non-negative integer for rolling_ic series item {point_index}",
        )
    return None
