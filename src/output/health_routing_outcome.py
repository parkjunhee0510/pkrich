"""Health checks for routing outcome output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_number_or_none,
    _load_json_object,
)
from src.output.health_routing_outcome_latest import _validate_routing_latest_run


_ROUTING_OUTCOME_STATUSES = {"ok", "no_data"}


def _validate_routing_outcome_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "routing_outcome.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {
        "schema_version",
        "run_count",
        "evaluated_signals",
        "latest_run_date",
        "summary",
        "periods",
        "status",
    }
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                "missing one of schema_version/run_count/evaluated_signals/latest_run_date/summary/periods/status",
            ),
        )

    for field in ("schema_version", "run_count", "evaluated_signals"):
        if not _is_non_negative_int(payload.get(field)):
            return (
                OutputHealthIssue(
                    "invalid_routing_outcome",
                    str(path),
                    f"{field} must be a non-negative integer",
                ),
            )
    if not isinstance(payload.get("latest_run_date"), str):
        return (
            OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                "latest_run_date must be a string",
            ),
        )
    if payload.get("status") not in _ROUTING_OUTCOME_STATUSES:
        return (
            OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                "status must be one of ok/no_data",
            ),
        )

    issue = _validate_routing_summary(path, "summary", payload.get("summary"))
    if issue is not None:
        return (issue,)

    periods = payload.get("periods")
    if not isinstance(periods, list):
        return (
            OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                "periods must be a list",
            ),
        )
    for index, period in enumerate(periods):
        if not isinstance(period, dict):
            return (
                OutputHealthIssue(
                    "invalid_routing_outcome",
                    str(path),
                    f"periods item {index} must be an object",
                ),
            )
        if not isinstance(period.get("period"), str):
            return (
                OutputHealthIssue(
                    "invalid_routing_outcome",
                    str(path),
                    f"period must be a string for periods item {index}",
                ),
            )
        issue = _validate_routing_summary(path, f"periods item {index}", period)
        if issue is not None:
            return (issue,)

    latest_run = payload.get("latest_run")
    if latest_run is not None:
        if not isinstance(latest_run, dict):
            return (
                OutputHealthIssue(
                    "invalid_routing_outcome",
                    str(path),
                    "latest_run must be an object",
                ),
            )
        if latest_run:
            issue = _validate_routing_latest_run(path, latest_run)
            if issue is not None:
                return (issue,)

    return ()


def _validate_routing_summary(path: Path, label: str, summary: object) -> OutputHealthIssue | None:
    count_fields = (
        "deep_selected_count",
        "economy_only_count",
        "portfolio_priority_count",
    )
    metric_fields = (
        "deep_selected_avg_return_20d",
        "economy_only_avg_return_20d",
        "portfolio_priority_avg_return_20d",
        "deep_selected_hit_rate",
        "economy_only_hit_rate",
        "portfolio_priority_hit_rate",
        "avg_return_delta_20d",
        "hit_rate_delta",
    )
    required = {*count_fields, *metric_fields}
    if not isinstance(summary, dict) or not required.issubset(summary.keys()):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            f"{label} missing routing summary fields",
        )
    for field in count_fields:
        if not _is_non_negative_int(summary.get(field)):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a non-negative integer for {label}",
            )
    for field in metric_fields:
        if not _is_number_or_none(summary.get(field)):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a number or null for {label}",
            )
    return None
