"""Health checks for generated output artifacts and web mirrors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.output.health_analysis_quality import _validate_analysis_quality_artifact
from src.output.health_analysis_performance import _validate_analysis_performance_artifact
from src.output.health_api_status import _validate_api_status_artifacts
from src.output.health_backtest_summary import _validate_backtest_summary_artifact
from src.output.health_common import OutputHealthIssue
from src.output.health_cost_log import _validate_cost_log_artifact
from src.output.health_file_integrity import (
    _compare_web_mirror,
    _detect_conflict_markers,
    _validate_json_tree,
)
from src.output.health_monthly_summary import _validate_monthly_summary_artifact
from src.output.health_operational_artifacts import validate_operational_artifacts
from src.output.health_operational_metrics import collect_operational_metric_warnings
from src.output.health_performance import _validate_performance_artifacts
from src.output.health_risk_intel import _validate_risk_intel_artifacts
from src.output.health_routing_outcome import _validate_routing_outcome_artifact
from src.output.health_search_audit import _validate_search_audit_artifact
from src.output.health_search_evidence import _validate_search_evidence_artifact
from src.output.health_signal_quality import _validate_signal_quality_artifact
from src.output.health_strategy_simulator import _validate_strategy_simulator_artifact
from src.output.health_validation_warnings import _validate_validation_warnings_artifact


@dataclass(frozen=True)
class OutputHealthResult:
    issues: tuple[OutputHealthIssue, ...]
    warnings: tuple[OutputHealthIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_summary(self, *, max_issues: int = 50) -> str:
        if self.ok:
            lines = ["output health check passed"]
        else:
            lines = [f"output health check failed: {len(self.issues)} issue(s)"]
            for issue in self.issues[:max_issues]:
                lines.append(f"- {issue.code}: {issue.path} ({issue.detail})")
            remaining = len(self.issues) - max_issues
            if remaining > 0:
                lines.append(f"- ... {remaining} more issue(s)")

        if self.warnings:
            lines.append(f"output health check warning(s): {len(self.warnings)}")
            for warning in self.warnings[:max_issues]:
                lines.append(f"- {warning.code}: {warning.path} ({warning.detail})")
            remaining_warnings = len(self.warnings) - max_issues
            if remaining_warnings > 0:
                lines.append(f"- ... {remaining_warnings} more warning(s)")
        return "\n".join(lines)


def check_output_health(
    project_root: str | Path = ".",
    *,
    source_data_dir: str | Path | None = None,
    web_data_dir: str | Path | None = None,
) -> OutputHealthResult:
    """Validate generated JSON and default web-public mirror consistency."""
    root = Path(project_root)
    source_root = Path(source_data_dir) if source_data_dir is not None else root / "output" / "data"
    mirror_root = Path(web_data_dir) if web_data_dir is not None else root / "web" / "public" / "output" / "data"

    issues: list[OutputHealthIssue] = []
    warnings: list[OutputHealthIssue] = []
    issues.extend(_validate_json_tree(source_root, label="output_data"))
    issues.extend(_validate_json_tree(mirror_root, label="web_public_output_data"))
    issues.extend(_validate_api_status_artifacts(source_root))
    issues.extend(_validate_validation_warnings_artifact(source_root))
    issues.extend(_validate_signal_quality_artifact(source_root))
    issues.extend(_validate_search_evidence_artifact(source_root))
    issues.extend(_validate_search_audit_artifact(source_root))
    issues.extend(_validate_backtest_summary_artifact(source_root))
    issues.extend(_validate_monthly_summary_artifact(source_root))
    issues.extend(_validate_routing_outcome_artifact(source_root))
    issues.extend(_validate_cost_log_artifact(source_root))
    issues.extend(_validate_analysis_quality_artifact(source_root))
    issues.extend(_validate_analysis_performance_artifact(source_root))
    issues.extend(_validate_strategy_simulator_artifact(source_root))
    issues.extend(_validate_performance_artifacts(source_root))
    issues.extend(_validate_risk_intel_artifacts(source_root, web_data_dir=mirror_root))
    artifact_issues, artifact_warnings = validate_operational_artifacts(
        project_root=root,
        source_root=source_root,
        mirror_root=mirror_root,
    )
    issues.extend(artifact_issues)
    warnings.extend(artifact_warnings)
    warnings.extend(collect_operational_metric_warnings(source_root))
    issues.extend(_detect_conflict_markers(source_root))
    issues.extend(_detect_conflict_markers(mirror_root))
    issues.extend(_compare_web_mirror(source_root, mirror_root))
    return OutputHealthResult(tuple(issues), tuple(warnings))
