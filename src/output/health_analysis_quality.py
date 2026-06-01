"""Health checks for analysis quality artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_number,
    _is_probability,
    _load_json_object,
)


def _validate_analysis_quality_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "analysis_quality.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "runs", "latest"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_analysis_quality",
                str(path),
                "missing one of schema_version/runs/latest",
            ),
        )
    if not _is_non_negative_int(payload.get("schema_version")):
        return (
            OutputHealthIssue(
                "invalid_analysis_quality",
                str(path),
                "schema_version must be a non-negative integer",
            ),
        )

    runs = payload.get("runs")
    if not isinstance(runs, list):
        return (
            OutputHealthIssue(
                "invalid_analysis_quality",
                str(path),
                "runs must be a list",
            ),
        )
    for index, run in enumerate(runs):
        issue = _validate_analysis_quality_run(path, f"runs item {index}", run)
        if issue is not None:
            return (issue,)

    latest = payload.get("latest")
    if not isinstance(latest, dict):
        return (
            OutputHealthIssue(
                "invalid_analysis_quality",
                str(path),
                "latest must be an object",
            ),
        )
    if latest:
        issue = _validate_analysis_quality_run(path, "latest", latest)
        if issue is not None:
            return (issue,)

    return ()


def _validate_analysis_quality_run(path: Path, label: str, run: object) -> OutputHealthIssue | None:
    count_fields = (
        "batch_count",
        "validated_ticker_count",
        "validation_failure_count",
        "schema_violation_count",
        "fact_warning_count",
        "consistency_warning_count",
        "hallucination_warning_count",
    )
    required = {
        "run_date",
        "success",
        "daily_api_cost_usd",
        "hallucination_ratio",
        *count_fields,
    }
    if not isinstance(run, dict) or not required.issubset(run.keys()):
        return OutputHealthIssue(
            "invalid_analysis_quality",
            str(path),
            f"{label} missing analysis quality run fields",
        )
    if not isinstance(run.get("run_date"), str) or not run.get("run_date", "").strip():
        return OutputHealthIssue(
            "invalid_analysis_quality",
            str(path),
            f"run_date must be a non-empty string for {label}",
        )
    if not isinstance(run.get("success"), bool):
        return OutputHealthIssue(
            "invalid_analysis_quality",
            str(path),
            f"success must be a boolean for {label}",
        )
    if not _is_non_negative_number(run.get("daily_api_cost_usd")):
        return OutputHealthIssue(
            "invalid_analysis_quality",
            str(path),
            f"daily_api_cost_usd must be a non-negative number for {label}",
        )
    for field in count_fields:
        if not _is_non_negative_int(run.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_quality",
                str(path),
                f"{field} must be a non-negative integer for {label}",
            )
    if not _is_probability(run.get("hallucination_ratio")):
        return OutputHealthIssue(
            "invalid_analysis_quality",
            str(path),
            f"hallucination_ratio must be a number from 0 to 1 for {label}",
        )
    return None
