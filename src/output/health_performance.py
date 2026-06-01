"""Health checks for performance measurement artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _load_json_object,
)
from src.output.health_performance_baseline import _validate_performance_baseline_payload
from src.output.health_performance_trends import _validate_performance_trends_payload
from src.output.health_quality_reliability_loop import _validate_quality_reliability_loop_artifact


def _validate_performance_artifacts(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    issues: list[OutputHealthIssue] = []
    baseline_path = root / "performance_baseline.json"
    if baseline_path.exists():
        baseline = _load_json_object(baseline_path)
        issues.extend(_validate_performance_baseline_payload(baseline_path, baseline))

    trends_path = root / "performance_trends.json"
    if trends_path.exists():
        trends = _load_json_object(trends_path)
        issue = _validate_performance_trends_payload(trends_path, trends)
        if issue is not None:
            issues.append(issue)

    issues.extend(_validate_quality_reliability_loop_artifact(root))

    return tuple(issues)
