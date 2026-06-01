"""Health checks for analysis performance factor attribution."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_number_or_none,
)


def _validate_analysis_performance_factor_attribution(path: Path, payload: dict) -> OutputHealthIssue | None:
    attribution = payload.get("factor_attribution")
    required = {"status", "missing_factor_sample_count", "factors"}
    if not isinstance(attribution, dict) or not required.issubset(attribution.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "factor_attribution missing status/missing_factor_sample_count/factors",
        )
    if not isinstance(attribution.get("status"), str) or not attribution.get("status", "").strip():
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "status must be a non-empty string for factor_attribution",
        )
    if not _is_non_negative_int(attribution.get("missing_factor_sample_count")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "missing_factor_sample_count must be a non-negative integer for factor_attribution",
        )
    factors = attribution.get("factors")
    if not isinstance(factors, dict):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            "factors must be an object for factor_attribution",
        )
    for factor, stats in factors.items():
        if not isinstance(factor, str) or not factor.strip():
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                "factor_attribution factor keys must be non-empty strings",
            )
        issue = _validate_analysis_performance_factor_stats(path, factor, stats)
        if issue is not None:
            return issue
    return None


def _validate_analysis_performance_factor_stats(
    path: Path,
    factor: str,
    stats: object,
) -> OutputHealthIssue | None:
    count_fields = ("sample_count", "positive_score_count", "negative_score_count")
    number_fields = ("avg_score", "avg_forward_return_5d", "avg_forward_return_20d")
    required = {*count_fields, *number_fields}
    if not isinstance(stats, dict) or not required.issubset(stats.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"factors {factor} missing factor stats",
        )
    for field in count_fields:
        if not _is_non_negative_int(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a non-negative integer for factor {factor}",
            )
    for field in number_fields:
        if not _is_number_or_none(stats.get(field)):
            return OutputHealthIssue(
                "invalid_analysis_performance",
                str(path),
                f"{field} must be a number or null for factor {factor}",
            )
    for field in ("best_action_context", "worst_action_context"):
        if field in stats:
            issue = _validate_analysis_performance_action_context(path, factor, field, stats.get(field))
            if issue is not None:
                return issue
    return None


def _validate_analysis_performance_action_context(
    path: Path,
    factor: str,
    field: str,
    context: object,
) -> OutputHealthIssue | None:
    required = {"action", "sample_count", "avg_return_5d"}
    if not isinstance(context, dict) or not required.issubset(context.keys()):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"{field} must include action/sample_count/avg_return_5d for factor {factor}",
        )
    if not isinstance(context.get("action"), str):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"action must be a string for {field} factor {factor}",
        )
    if not _is_non_negative_int(context.get("sample_count")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"sample_count must be a non-negative integer for {field} factor {factor}",
        )
    if not _is_number_or_none(context.get("avg_return_5d")):
        return OutputHealthIssue(
            "invalid_analysis_performance",
            str(path),
            f"avg_return_5d must be a number or null for {field} factor {factor}",
        )
    return None
