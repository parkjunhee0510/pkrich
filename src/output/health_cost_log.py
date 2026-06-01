"""Health checks for cost log artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _load_json_object,
)
from src.output.health_cost_log_run import _validate_cost_log_run


def _validate_cost_log_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "cost_log.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "runs", "latest"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                "missing one of schema_version/runs/latest",
            ),
        )
    if not _is_non_negative_int(payload.get("schema_version")):
        return (
            OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                "schema_version must be a non-negative integer",
            ),
        )

    runs = payload.get("runs")
    if not isinstance(runs, list):
        return (
            OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                "runs must be a list",
            ),
        )
    for index, run in enumerate(runs):
        issue = _validate_cost_log_run(path, f"runs item {index}", run)
        if issue is not None:
            return (issue,)

    latest = payload.get("latest")
    if not isinstance(latest, dict):
        return (
            OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                "latest must be an object",
            ),
        )
    if latest:
        issue = _validate_cost_log_run(path, "latest", latest)
        if issue is not None:
            return (issue,)

    return ()
