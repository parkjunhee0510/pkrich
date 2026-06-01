"""Health checks for validation warnings output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _load_json_object,
)


def _validate_validation_warnings_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "validation_warnings.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "window_days", "generated_at", "categories", "totals", "series"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "missing one of schema_version/window_days/generated_at/categories/totals/series",
            ),
        )
    if not _is_non_negative_int(payload.get("schema_version")):
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "schema_version must be a non-negative integer",
            ),
        )
    if not _is_non_negative_int(payload.get("window_days")):
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "window_days must be a non-negative integer",
            ),
        )
    if not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at", "").strip():
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "generated_at must be a non-empty string",
            ),
        )

    categories = payload.get("categories")
    if not isinstance(categories, list) or not categories or not all(isinstance(item, str) and item.strip() for item in categories):
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "categories must be a non-empty list of strings",
            ),
        )

    totals = payload.get("totals")
    if not isinstance(totals, dict):
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "totals must be an object",
            ),
        )
    for category in categories:
        if not _is_non_negative_int(totals.get(category)):
            return (
                OutputHealthIssue(
                    "invalid_validation_warnings",
                    str(path),
                    f"totals {category} must be a non-negative integer",
                ),
            )

    series = payload.get("series")
    if not isinstance(series, list):
        return (
            OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                "series must be a list",
            ),
        )
    for index, row in enumerate(series):
        issue = _validate_validation_warning_series_row(path, index, row, categories)
        if issue is not None:
            return (issue,)

    return ()


def _validate_validation_warning_series_row(
    path: Path,
    index: int,
    row: object,
    categories: list[str],
) -> OutputHealthIssue | None:
    required_base_fields = {"date", "batch_count", "validated_ticker_count", "validation_failure_count"}
    if not isinstance(row, dict) or not required_base_fields.issubset(row.keys()):
        return OutputHealthIssue(
            "invalid_validation_warnings",
            str(path),
            f"series item {index} missing date/batch_count/validated_ticker_count/validation_failure_count",
        )
    if not isinstance(row.get("date"), str) or not row.get("date", "").strip():
        return OutputHealthIssue(
            "invalid_validation_warnings",
            str(path),
            f"date must be a non-empty string for series item {index}",
        )
    for field in ("batch_count", "validated_ticker_count", "validation_failure_count"):
        if not _is_non_negative_int(row.get(field)):
            return OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                f"{field} must be a non-negative integer for series item {index}",
            )
    for category in categories:
        if not _is_non_negative_int(row.get(category)):
            return OutputHealthIssue(
                "invalid_validation_warnings",
                str(path),
                f"{category} must be a non-negative integer for series item {index}",
            )
    return None
