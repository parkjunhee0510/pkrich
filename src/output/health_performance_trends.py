"""Health checks for performance trend artifacts."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_number,
    _is_probability,
)


def _validate_performance_trends_payload(path: Path, payload: dict) -> OutputHealthIssue | None:
    required = {"schema_version", "as_of", "monthly_budget_usd", "runs"}
    if not required.issubset(payload.keys()):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            "missing one of schema_version/as_of/monthly_budget_usd/runs",
        )
    if not _is_non_negative_int(payload.get("schema_version")):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            "schema_version must be a non-negative integer",
        )
    if not isinstance(payload.get("as_of"), str) or not payload.get("as_of", "").strip():
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            "as_of must be a non-empty string",
        )
    if not _is_non_negative_number(payload.get("monthly_budget_usd")):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            "monthly_budget_usd must be a non-negative number",
        )
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            "runs must be a list",
        )
    for index, run in enumerate(runs):
        issue = _validate_performance_trend_run(path, index, run)
        if issue is not None:
            return issue
    return None


def _validate_performance_trend_run(path: Path, index: int, run: object) -> OutputHealthIssue | None:
    count_fields = (
        "llm_calls",
        "validation_failure_count",
        "deep_selected_count",
        "budget_guard_would_block_count",
    )
    required = {"run_date", "success", "total_cost_usd", "hallucination_ratio", *count_fields}
    if not isinstance(run, dict) or not required.issubset(run.keys()):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            f"runs item {index} missing run_date/success/total_cost_usd/llm_calls/hallucination_ratio/count fields",
        )
    if not isinstance(run.get("run_date"), str) or not run.get("run_date", "").strip():
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            f"run_date must be a non-empty string for runs item {index}",
        )
    if not isinstance(run.get("success"), bool):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            f"success must be a boolean for runs item {index}",
        )
    if not _is_non_negative_number(run.get("total_cost_usd")):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            f"total_cost_usd must be a non-negative number for runs item {index}",
        )
    if not _is_probability(run.get("hallucination_ratio")):
        return OutputHealthIssue(
            "invalid_performance_trends",
            str(path),
            f"hallucination_ratio must be a number from 0 to 1 for runs item {index}",
        )
    for field in count_fields:
        if not _is_non_negative_int(run.get(field)):
            return OutputHealthIssue(
                "invalid_performance_trends",
                str(path),
                f"{field} must be a non-negative integer for runs item {index}",
            )
    return None
