"""Health checks for signal quality artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _load_json_object,
)
from src.output.health_signal_quality_ic import (
    _validate_signal_ic_decay,
    _validate_signal_rolling_ic,
)
from src.output.health_signal_quality_risk import (
    _validate_signal_kelly,
    _validate_signal_turnover,
)


def _validate_signal_quality_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "signal_quality.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    if not _is_non_negative_int(payload.get("schema_version")):
        return (
            OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                "schema_version must be a non-negative integer",
            ),
        )

    if "error" in payload:
        if not isinstance(payload.get("error"), str):
            return (
                OutputHealthIssue(
                    "invalid_signal_quality",
                    str(path),
                    "error must be a string",
                ),
            )
        return ()

    required = {"ic_decay", "rolling_ic", "kelly", "turnover"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                "missing one of ic_decay/rolling_ic/kelly/turnover",
            ),
        )

    validators = (
        _validate_signal_ic_decay,
        _validate_signal_rolling_ic,
        _validate_signal_kelly,
        _validate_signal_turnover,
    )
    for validator in validators:
        issue = validator(path, payload)
        if issue is not None:
            return (issue,)
    return ()
