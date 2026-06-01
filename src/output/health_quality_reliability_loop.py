"""Health checks for quality reliability loop artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_non_negative_number,
    _is_probability,
    _is_string_list,
    _load_json_object,
)


_STATUS_VALUES = {
    "ok",
    "partial",
    "warning",
    "failed",
    "insufficient_data",
    "missing",
    "reported",
}
_JSON_HEALTH_STATUS_VALUES = {"ok", "invalid_json", "missing"}


def _validate_quality_reliability_loop_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "quality_reliability_loop.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    return tuple(_validate_quality_reliability_loop_payload(path, payload))


def _validate_quality_reliability_loop_payload(
    path: Path,
    payload: dict[str, Any],
) -> list[OutputHealthIssue]:
    required = {
        "schema_version",
        "as_of",
        "status",
        "summary",
        "decision_quality",
        "artifact_reliability",
        "evidence_quality",
        "cost_and_runtime",
        "trend_inputs",
        "warnings",
    }
    if not required.issubset(payload.keys()):
        return [
            _issue(
                path,
                "missing one of schema_version/as_of/status/summary/decision_quality/artifact_reliability/evidence_quality/cost_and_runtime/trend_inputs/warnings",
            )
        ]

    issues: list[OutputHealthIssue] = []
    if not _is_positive_int(payload.get("schema_version")):
        issues.append(_issue(path, "schema_version must be a positive integer"))
    if not _is_non_empty_string(payload.get("as_of")):
        issues.append(_issue(path, "as_of must be a non-empty string"))
    if payload.get("status") not in _STATUS_VALUES:
        issues.append(_issue(path, "status must be a known quality reliability loop status"))

    for field in (
        "summary",
        "decision_quality",
        "artifact_reliability",
        "evidence_quality",
        "cost_and_runtime",
        "trend_inputs",
    ):
        if not isinstance(payload.get(field), dict):
            issues.append(_issue(path, f"{field} must be an object"))

    if not _is_string_list(payload.get("warnings")):
        issues.append(_issue(path, "warnings must be a list of strings"))

    summary = payload.get("summary")
    if isinstance(summary, dict):
        issues.extend(_validate_summary(path, summary))

    decision_quality = payload.get("decision_quality")
    if isinstance(decision_quality, dict):
        issues.extend(_validate_decision_quality(path, decision_quality))

    artifact_reliability = payload.get("artifact_reliability")
    if isinstance(artifact_reliability, dict):
        issues.extend(_validate_artifact_reliability(path, artifact_reliability))

    evidence_quality = payload.get("evidence_quality")
    if isinstance(evidence_quality, dict):
        issues.extend(_validate_evidence_quality(path, evidence_quality))

    cost_and_runtime = payload.get("cost_and_runtime")
    if isinstance(cost_and_runtime, dict):
        issues.extend(_validate_cost_and_runtime(path, cost_and_runtime))

    trend_inputs = payload.get("trend_inputs")
    if isinstance(trend_inputs, dict):
        issues.extend(_validate_trend_inputs(path, trend_inputs))

    return issues


def _validate_summary(path: Path, summary: dict[str, Any]) -> list[OutputHealthIssue]:
    status_fields = (
        "decision_quality_status",
        "artifact_reliability_status",
        "evidence_status",
        "cost_status",
    )
    required = {*status_fields}
    if not required.issubset(summary.keys()):
        return [
            _issue(
                path,
                "summary missing decision_quality_status/artifact_reliability_status/evidence_status/cost_status",
            )
        ]

    issues: list[OutputHealthIssue] = []
    for field in status_fields:
        if summary.get(field) not in _STATUS_VALUES:
            issues.append(_issue(path, f"{field} must be a known status for summary"))
    if "notes" in summary and not _is_string_list(summary.get("notes")):
        issues.append(_issue(path, "notes must be a list of strings for summary"))
    return issues


def _validate_decision_quality(path: Path, decision_quality: dict[str, Any]) -> list[OutputHealthIssue]:
    count_fields = (
        "sample_count",
        "completed_return_window_count",
        "evaluated_signal_window_count",
        "populated_conviction_bucket_count",
        "factor_count",
    )
    ratio_fields = (
        "action_change_coverage_ratio",
        "hallucination_ratio",
        "validation_failure_rate",
    )
    required = {"status", "loop_readiness_status", *count_fields, *ratio_fields}
    if not required.issubset(decision_quality.keys()):
        return [
            _issue(
                path,
                "decision_quality missing status/loop_readiness_status/count/ratio fields",
            )
    ]

    issues: list[OutputHealthIssue] = []
    if decision_quality.get("status") not in _STATUS_VALUES:
        issues.append(_issue(path, "status must be a known status for decision_quality"))
    if not isinstance(decision_quality.get("loop_readiness_status"), str):
        issues.append(_issue(path, "loop_readiness_status must be a string for decision_quality"))
    for field in count_fields:
        if not _is_non_negative_int(decision_quality.get(field)):
            issues.append(_issue(path, f"{field} must be a non-negative integer for decision_quality"))
    for field in ratio_fields:
        if not _is_probability(decision_quality.get(field)):
            issues.append(_issue(path, f"{field} must be a number from 0 to 1 for decision_quality"))
    return issues


def _validate_artifact_reliability(path: Path, artifact_reliability: dict[str, Any]) -> list[OutputHealthIssue]:
    required = {
        "status",
        "json_health_status",
        "invalid_json_count",
        "issue_count",
        "output_schema_status",
    }
    if not required.issubset(artifact_reliability.keys()):
        return [
            _issue(
                path,
                "artifact_reliability missing status/json_health_status/invalid_json_count/issue_count/output_schema_status",
            )
        ]

    issues: list[OutputHealthIssue] = []
    if artifact_reliability.get("status") not in _STATUS_VALUES:
        issues.append(_issue(path, "status must be a known status for artifact_reliability"))
    if artifact_reliability.get("json_health_status") not in _JSON_HEALTH_STATUS_VALUES:
        issues.append(_issue(path, "json_health_status must be ok, invalid_json, or missing for artifact_reliability"))
    if not _is_non_negative_int(artifact_reliability.get("invalid_json_count")):
        issues.append(
            _issue(path, "invalid_json_count must be a non-negative integer for artifact_reliability")
        )
    if not _is_non_negative_int(artifact_reliability.get("issue_count")):
        issues.append(_issue(path, "issue_count must be a non-negative integer for artifact_reliability"))
    if not isinstance(artifact_reliability.get("output_schema_status"), str):
        issues.append(_issue(path, "output_schema_status must be a string for artifact_reliability"))
    if "issues" in artifact_reliability and not isinstance(artifact_reliability.get("issues"), list):
        issues.append(_issue(path, "issues must be a list for artifact_reliability"))
    return issues


def _validate_evidence_quality(path: Path, evidence_quality: dict[str, Any]) -> list[OutputHealthIssue]:
    count_fields = (
        "ticker_count",
        "covered_ticker_count",
        "searched_ticker_count",
        "priority_ticker_count",
        "priority_covered_ticker_count",
        "priority_refresh_candidate_count",
        "priority_provider_error_count",
        "priority_not_refreshed_count",
        "priority_no_evidence_count",
        "operational_issue_count",
    )
    ratio_fields = ("coverage_ratio", "priority_coverage_ratio")
    mapping_fields = ("status_counts", "priority_status_counts", "priority_refresh_reasons")
    required = {
        "status",
        "provider_issue_status",
        *count_fields,
        *ratio_fields,
        *mapping_fields,
    }
    if not required.issubset(evidence_quality.keys()):
        return [
            _issue(
                path,
                "evidence_quality missing status/provider_issue_status/count/ratio/status map fields",
            )
        ]

    issues: list[OutputHealthIssue] = []
    if evidence_quality.get("status") not in _STATUS_VALUES:
        issues.append(_issue(path, "status must be a known status for evidence_quality"))
    if not isinstance(evidence_quality.get("provider_issue_status"), str):
        issues.append(_issue(path, "provider_issue_status must be a string for evidence_quality"))
    for field in count_fields:
        if not _is_non_negative_int(evidence_quality.get(field)):
            issues.append(_issue(path, f"{field} must be a non-negative integer for evidence_quality"))
    for field in ratio_fields:
        if not _is_probability(evidence_quality.get(field)):
            issues.append(_issue(path, f"{field} must be a number from 0 to 1 for evidence_quality"))
    for field in mapping_fields:
        if not _is_non_negative_int_mapping(evidence_quality.get(field)):
            issues.append(
                _issue(
                    path,
                    f"{field} must be an object with non-negative integer counts for evidence_quality",
                )
            )
    return issues


def _validate_cost_and_runtime(path: Path, cost_and_runtime: dict[str, Any]) -> list[OutputHealthIssue]:
    count_fields = (
        "llm_calls",
        "budget_guard_would_block_count",
        "budget_guard_blocked_count",
    )
    number_fields = (
        "total_cost_usd",
        "estimated_monthly_cost_usd",
        "llm_calls_per_ticker",
    )
    required = {
        "status",
        "cost_policy",
        "budget_guard_status",
        "budget_guard_mode",
        *count_fields,
        *number_fields,
    }
    if not required.issubset(cost_and_runtime.keys()):
        return [
            _issue(
                path,
                "cost_and_runtime missing status/cost_policy/cost/call/budget guard fields",
            )
        ]

    issues: list[OutputHealthIssue] = []
    if cost_and_runtime.get("status") not in _STATUS_VALUES:
        issues.append(_issue(path, "status must be a known status for cost_and_runtime"))
    if cost_and_runtime.get("cost_policy") != "report_only":
        issues.append(_issue(path, "cost_policy must be report_only for cost_and_runtime"))
    for field in ("budget_guard_status", "budget_guard_mode"):
        if not isinstance(cost_and_runtime.get(field), str):
            issues.append(_issue(path, f"{field} must be a string for cost_and_runtime"))
    for field in number_fields:
        if not _is_non_negative_number(cost_and_runtime.get(field)):
            issues.append(_issue(path, f"{field} must be a non-negative number for cost_and_runtime"))
    for field in count_fields:
        if not _is_non_negative_int(cost_and_runtime.get(field)):
            issues.append(_issue(path, f"{field} must be a non-negative integer for cost_and_runtime"))
    return issues


def _validate_trend_inputs(path: Path, trend_inputs: dict[str, Any]) -> list[OutputHealthIssue]:
    required = {
        "run_count",
        "latest_run_date",
    }
    if not required.issubset(trend_inputs.keys()):
        return [_issue(path, "trend_inputs missing run_count/latest_run_date")]

    issues: list[OutputHealthIssue] = []
    if not _is_non_negative_int(trend_inputs.get("run_count")):
        issues.append(_issue(path, "run_count must be a non-negative integer for trend_inputs"))
    if not isinstance(trend_inputs.get("latest_run_date"), str):
        issues.append(_issue(path, "latest_run_date must be a string for trend_inputs"))
    for field in ("trend_start_date", "trend_end_date"):
        if field in trend_inputs and not isinstance(trend_inputs.get(field), str):
            issues.append(_issue(path, f"{field} must be a string for trend_inputs"))
    return issues


def _issue(path: Path, detail: str) -> OutputHealthIssue:
    return OutputHealthIssue("invalid_quality_reliability_loop", str(path), detail)


def _is_positive_int(value: object) -> bool:
    return _is_non_negative_int(value) and value > 0


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
