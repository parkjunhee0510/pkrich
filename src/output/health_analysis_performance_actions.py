"""Health checks for analysis performance action-change reasons."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_number_or_none,
    _is_string_list,
)


def _validate_analysis_performance_action_changes(path: Path, payload: dict) -> OutputHealthIssue | None:
    changes = payload.get("action_change_reasons")
    if not isinstance(changes, list):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "action_change_reasons must be a list",
        )
    for index, change in enumerate(changes):
        issue = _validate_analysis_performance_action_change(path, index, change)
        if issue is not None:
            return issue
    return None


def _validate_analysis_performance_action_change(
    path: Path,
    index: int,
    change: object,
) -> OutputHealthIssue | None:
    string_fields = (
        "ticker",
        "previous_action",
        "current_action",
        "previous_regime",
        "current_regime",
        "summary",
    )
    required = {
        *string_fields,
        "previous_conviction",
        "current_conviction",
        "reason_codes",
        "contributors",
    }
    if not isinstance(change, dict) or not required.issubset(change.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"action_change_reasons item {index} missing required fields",
        )
    for field in string_fields:
        if not isinstance(change.get(field), str):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a string for action_change_reasons item {index}",
            )
    for field in ("previous_conviction", "current_conviction"):
        if not _is_number_or_none(change.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number or null for action_change_reasons item {index}",
            )
    if not _is_string_list(change.get("reason_codes")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"reason_codes must be a list of strings for action_change_reasons item {index}",
        )
    contributors = change.get("contributors")
    if not isinstance(contributors, list):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"contributors must be a list for action_change_reasons item {index}",
        )
    for contributor_index, contributor in enumerate(contributors):
        issue = _validate_analysis_performance_contributor(path, index, contributor_index, contributor)
        if issue is not None:
            return issue
    return None


def _validate_analysis_performance_contributor(
    path: Path,
    change_index: int,
    contributor_index: int,
    contributor: object,
) -> OutputHealthIssue | None:
    required = {"factor", "previous", "current"}
    if not isinstance(contributor, dict) or not required.issubset(contributor.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"contributors item {contributor_index} missing factor/previous/current for action_change_reasons item {change_index}",
        )
    if not isinstance(contributor.get("factor"), str) or not contributor.get("factor", "").strip():
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"factor must be a non-empty string for contributors item {contributor_index}",
        )
    for field in ("previous", "current"):
        if not _is_number_or_none(contributor.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number or null for contributors item {contributor_index}",
            )
    return None
