"""Health checks for performance baseline artifacts."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_non_negative_number,
    _is_probability,
    _is_string_list,
)


def _validate_performance_baseline_payload(path: Path, payload: dict) -> tuple[OutputHealthIssue, ...]:
    required = {
        "schema_version",
        "as_of",
        "status",
        "latest_run_date",
        "monthly_budget_usd",
        "json_health",
        "cost",
        "quality",
        "evidence",
        "signals",
    }
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                "missing one of schema_version/as_of/status/latest_run_date/monthly_budget_usd/json_health/cost/quality/evidence/signals",
            ),
        )

    issues: list[OutputHealthIssue] = []
    if not _is_non_negative_int(payload.get("schema_version")):
        issues.append(
            OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                "schema_version must be a non-negative integer",
            )
        )
    for field in ("as_of", "status"):
        if not isinstance(payload.get(field), str) or not payload.get(field, "").strip():
            issues.append(
                OutputHealthIssue(
                    "invalid_performance_baseline",
                    str(path),
                    f"{field} must be a non-empty string",
                )
            )
    latest_run_date = payload.get("latest_run_date")
    if not isinstance(latest_run_date, str) or (
        not latest_run_date.strip() and payload.get("status") != "insufficient_data"
    ):
        issues.append(
            OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                "latest_run_date must be a non-empty string unless status is insufficient_data",
            )
        )
    if not _is_non_negative_number(payload.get("monthly_budget_usd")):
        issues.append(
            OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                "monthly_budget_usd must be a non-negative number",
            )
        )

    for validator in (
        _validate_performance_baseline_cost,
        _validate_performance_baseline_quality,
        _validate_performance_baseline_evidence,
        _validate_performance_baseline_signals,
        _validate_performance_baseline_p1_readiness,
    ):
        issue = validator(path, payload)
        if issue is not None:
            issues.append(issue)

    return tuple(issues)


def _validate_performance_baseline_cost(path: Path, payload: dict) -> OutputHealthIssue | None:
    cost = payload.get("cost")
    count_fields = (
        "llm_calls",
        "ticker_count_for_rate",
        "deep_selected_count",
        "routing_conflicted_count",
        "budget_guard_would_block_count",
        "budget_guard_blocked_count",
    )
    number_fields = (
        "total_cost_usd",
        "estimated_monthly_cost_usd",
        "monthly_budget_usd",
        "budget_usage_ratio",
        "llm_calls_per_ticker",
    )
    required = {*count_fields, *number_fields}
    if not isinstance(cost, dict) or not required.issubset(cost.keys()):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "cost missing total/monthly/budget/call/routing fields",
        )
    for field in number_fields:
        if not _is_non_negative_number(cost.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a non-negative number for cost",
            )
    for field in count_fields:
        if not _is_non_negative_int(cost.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a non-negative integer for cost",
            )
    return None


def _validate_performance_baseline_quality(path: Path, payload: dict) -> OutputHealthIssue | None:
    quality = payload.get("quality")
    count_fields = (
        "validated_ticker_count",
        "validation_failure_count",
        "hallucination_warning_count",
        "fact_warning_count",
        "consistency_warning_count",
    )
    rate_fields = ("validation_failure_rate", "hallucination_ratio")
    required = {*count_fields, *rate_fields}
    if not isinstance(quality, dict) or not required.issubset(quality.keys()):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "quality missing validation/hallucination/fact/consistency fields",
        )
    for field in count_fields:
        if not _is_non_negative_int(quality.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a non-negative integer for quality",
            )
    for field in rate_fields:
        if not _is_probability(quality.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a number from 0 to 1 for quality",
            )
    return None


def _validate_performance_baseline_evidence(path: Path, payload: dict) -> OutputHealthIssue | None:
    evidence = payload.get("evidence")
    count_fields = (
        "ticker_count",
        "covered_ticker_count",
        "candidate_ticker_count",
        "searched_ticker_count",
        "cache_ttl_hours",
        "cache_hit_count",
        "stale_cache_hit_count",
        "max_cache_age_hours",
        "provider_candidate_count",
        "priority_ticker_count",
        "priority_covered_ticker_count",
        "priority_refresh_candidate_count",
        "priority_provider_error_count",
        "priority_not_refreshed_count",
        "priority_no_evidence_count",
    )
    ratio_fields = (
        "coverage_ratio",
        "average_coverage_score",
        "average_freshness_score",
        "cache_hit_ratio",
        "stale_cache_hit_ratio",
        "priority_coverage_ratio",
    )
    number_fields = ("average_cache_age_hours",)
    mapping_fields = ("status_counts", "priority_status_counts", "priority_refresh_reasons")
    required = {
        "provider",
        *count_fields,
        *ratio_fields,
        *number_fields,
        *mapping_fields,
    }
    cache_fields = {
        "cache_ttl_hours",
        "cache_hit_count",
        "stale_cache_hit_count",
        "average_cache_age_hours",
        "max_cache_age_hours",
    }
    if not isinstance(evidence, dict) or not cache_fields.issubset(evidence.keys()):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "missing evidence cache freshness fields",
        )
    if not required.issubset(evidence.keys()):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "evidence missing provider/count/ratio/status fields",
        )
    if not isinstance(evidence.get("provider"), str):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "provider must be a string for evidence",
        )
    for field in count_fields:
        if not _is_non_negative_int(evidence.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a non-negative integer for evidence",
            )
    for field in ratio_fields:
        if not _is_probability(evidence.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a number from 0 to 1 for evidence",
            )
    for field in number_fields:
        if not _is_non_negative_number(evidence.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a non-negative number for evidence",
            )
    for field in mapping_fields:
        if not _is_non_negative_int_mapping(evidence.get(field)):
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be an object with non-negative integer counts for evidence",
            )
    return None


def _validate_performance_baseline_signals(path: Path, payload: dict) -> OutputHealthIssue | None:
    signals = payload.get("signals")
    required = {"turnover_status", "avg_turnover", "kelly_status"}
    if not isinstance(signals, dict) or not required.issubset(signals.keys()):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "signals missing turnover_status/avg_turnover/kelly_status",
        )
    for field in ("turnover_status", "kelly_status"):
        if not isinstance(signals.get(field), str) or not signals.get(field, "").strip():
            return OutputHealthIssue(
                "invalid_performance_baseline",
                str(path),
                f"{field} must be a non-empty string for signals",
            )
    if not _is_probability(signals.get("avg_turnover")):
        return OutputHealthIssue(
            "invalid_performance_baseline",
            str(path),
            "avg_turnover must be a number from 0 to 1 for signals",
        )
    return None


def _validate_performance_baseline_p1_readiness(
    path: Path,
    payload: dict,
) -> OutputHealthIssue | None:
    if "p1_readiness" not in payload:
        return None

    p1_readiness = payload.get("p1_readiness")
    if not isinstance(p1_readiness, dict):
        return _performance_baseline_issue(path, "p1_readiness must be an object")
    if not _is_non_empty_string(p1_readiness.get("status")):
        return _performance_baseline_issue(path, "status must be a non-empty string for p1_readiness")
    if not _is_non_empty_string(p1_readiness.get("mode")):
        return _performance_baseline_issue(path, "mode must be a non-empty string for p1_readiness")

    tracks = p1_readiness.get("tracks")
    required_tracks = {
        "search_evidence_provider",
        "budget_guard",
        "analysis_performance",
        "output_schema",
    }
    if not isinstance(tracks, dict):
        return _performance_baseline_issue(path, "tracks must be an object for p1_readiness")
    missing_tracks = sorted(required_tracks - tracks.keys())
    if missing_tracks:
        return _performance_baseline_issue(
            path,
            f"tracks missing {', '.join(missing_tracks)} for p1_readiness",
        )

    for validator in (
        _validate_p1_search_evidence_provider,
        _validate_p1_budget_guard,
        _validate_p1_analysis_performance,
        _validate_p1_output_schema,
    ):
        detail = validator(tracks)
        if detail is not None:
            return _performance_baseline_issue(path, detail)
    return None


def _validate_p1_search_evidence_provider(tracks: dict) -> str | None:
    track = tracks.get("search_evidence_provider")
    if not isinstance(track, dict):
        return "search_evidence_provider must be an object for p1_readiness"
    if not _is_non_empty_string(track.get("status")):
        return "status must be a non-empty string for search_evidence_provider"
    if not isinstance(track.get("provider"), str):
        return "provider must be a string for search_evidence_provider"
    for field in (
        "candidate_ticker_count",
        "priority_ticker_count",
        "searched_ticker_count",
        "provider_candidate_count",
        "provider_call_count",
        "cache_hit_count",
        "stale_cache_hit_count",
        "provider_error_count",
        "provider_unavailable_count",
        "cache_error_count",
        "skipped_ticker_count",
        "operational_issue_count",
    ):
        if not _is_non_negative_int(track.get(field)):
            return f"{field} must be a non-negative integer for search_evidence_provider"
    for field in ("cap_review_status", "provider_issue_status", "stale_cache_reuse_status"):
        if not _is_non_empty_string(track.get(field)):
            return f"{field} must be a non-empty string for search_evidence_provider"
    if not _is_probability(track.get("priority_refresh_candidate_ratio")):
        return "priority_refresh_candidate_ratio must be a number from 0 to 1 for search_evidence_provider"
    if not _is_non_negative_int_mapping(track.get("status_counts")):
        return "status_counts must be an object with non-negative integer counts for search_evidence_provider"
    return None


def _validate_p1_budget_guard(tracks: dict) -> str | None:
    track = tracks.get("budget_guard")
    if not isinstance(track, dict):
        return "budget_guard must be an object for p1_readiness"
    if not _is_non_empty_string(track.get("status")):
        return "status must be a non-empty string for budget_guard"
    if not isinstance(track.get("mode"), str):
        return "mode must be a string for budget_guard"
    if not _is_non_empty_string(track.get("enforce_review_status")):
        return "enforce_review_status must be a non-empty string for budget_guard"
    for field in ("decision_counts", "guarded_path_status_counts"):
        if not _is_non_negative_int_mapping(track.get(field)):
            return f"{field} must be an object with non-negative integer counts for budget_guard"
    for field in (
        "would_block_count",
        "blocked_count",
        "guarded_path_count",
        "would_block_path_count",
        "blocked_path_count",
        "allow_path_count",
    ):
        if not _is_non_negative_int(track.get(field)):
            return f"{field} must be a non-negative integer for budget_guard"
    if not _is_non_negative_number(track.get("total_estimated_incremental_cost_usd")):
        return "total_estimated_incremental_cost_usd must be a non-negative number for budget_guard"
    return None


def _validate_p1_analysis_performance(tracks: dict) -> str | None:
    track = tracks.get("analysis_performance")
    if not isinstance(track, dict):
        return "analysis_performance must be an object for p1_readiness"
    if not _is_non_empty_string(track.get("status")):
        return "status must be a non-empty string for analysis_performance"
    if not isinstance(track.get("mode"), str):
        return "mode must be a string for analysis_performance"
    for field in (
        "sample_count",
        "decision_count",
        "completed_return_window_count",
        "evaluated_signal_window_count",
        "conviction_bucket_count",
        "populated_conviction_bucket_count",
        "regime_count",
        "factor_count",
        "missing_factor_sample_count",
        "action_change_reason_count",
    ):
        if not _is_non_negative_int(track.get(field)):
            return f"{field} must be a non-negative integer for analysis_performance"
    if not _is_string_list(track.get("completed_return_windows")):
        return "completed_return_windows must be a string list for analysis_performance"
    for field in ("calibration_status", "factor_attribution_status", "loop_readiness_status"):
        if not _is_non_empty_string(track.get(field)):
            return f"{field} must be a non-empty string for analysis_performance"
    if not _is_probability(track.get("action_change_coverage_ratio")):
        return "action_change_coverage_ratio must be a number from 0 to 1 for analysis_performance"
    return None


def _validate_p1_output_schema(tracks: dict) -> str | None:
    track = tracks.get("output_schema")
    if not isinstance(track, dict):
        return "output_schema must be an object for p1_readiness"
    if not _is_non_empty_string(track.get("status")):
        return "status must be a non-empty string for output_schema"
    if not _is_non_empty_string(track.get("json_health_status")):
        return "json_health_status must be a non-empty string for output_schema"
    for field in ("invalid_json_count", "issue_count"):
        if not _is_non_negative_int(track.get(field)):
            return f"{field} must be a non-negative integer for output_schema"
    return None


def _performance_baseline_issue(path: Path, detail: str) -> OutputHealthIssue:
    return OutputHealthIssue(
        "invalid_performance_baseline",
        str(path),
        detail,
    )


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
