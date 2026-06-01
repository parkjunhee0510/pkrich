"""Health checks for cost log run rows."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_non_negative_number,
    _is_probability,
    _is_string_mapping,
)


def _validate_cost_log_run(path: Path, label: str, run: object) -> OutputHealthIssue | None:
    required = {
        "run_date",
        "success",
        "total_cost_usd",
        "profiles",
        "routing",
        "budget_guard",
        "deep_pass_value",
    }
    if not isinstance(run, dict) or not required.issubset(run.keys()):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"{label} missing cost log run fields",
        )
    if not isinstance(run.get("run_date"), str) or not run.get("run_date", "").strip():
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"run_date must be a non-empty string for {label}",
        )
    if not isinstance(run.get("success"), bool):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"success must be a boolean for {label}",
        )
    if not _is_non_negative_number(run.get("total_cost_usd")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"total_cost_usd must be a non-negative number for {label}",
        )

    profiles = run.get("profiles")
    if not isinstance(profiles, dict):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"profiles must be an object for {label}",
        )
    for profile_name, profile in profiles.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            return OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                f"profiles keys must be non-empty strings for {label}",
            )
        issue = _validate_cost_log_profile(path, label, profile_name, profile)
        if issue is not None:
            return issue

    issue = _validate_cost_log_routing(path, label, run.get("routing"))
    if issue is not None:
        return issue
    issue = _validate_cost_log_budget_guard(path, label, run.get("budget_guard"))
    if issue is not None:
        return issue
    issue = _validate_cost_log_deep_pass_value(path, label, run.get("deep_pass_value"))
    if issue is not None:
        return issue
    return None


def _validate_cost_log_profile(
    path: Path,
    label: str,
    profile_name: str,
    profile: object,
) -> OutputHealthIssue | None:
    count_fields = (
        "tokens",
        "input_tokens",
        "cached_input_tokens",
        "uncached_input_tokens",
        "calls",
    )
    required = {"cost_usd", "cache_hit_ratio", "models", *count_fields}
    if not isinstance(profile, dict) or not required.issubset(profile.keys()):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"profiles {profile_name} missing cost/token fields for {label}",
        )
    if not _is_non_negative_number(profile.get("cost_usd")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"cost_usd must be a non-negative number for {label} profile {profile_name}",
        )
    for field in count_fields:
        if not _is_non_negative_int(profile.get(field)):
            return OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                f"{field} must be a non-negative integer for {label} profile {profile_name}",
            )
    cache_hit_ratio = profile.get("cache_hit_ratio")
    if cache_hit_ratio is not None and not _is_probability(cache_hit_ratio):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"cache_hit_ratio must be a number from 0 to 1 or null for {label} profile {profile_name}",
        )
    if not _is_non_negative_int_mapping(profile.get("models")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"models must be an object with non-negative integer counts for {label} profile {profile_name}",
        )
    return None


def _validate_cost_log_routing(path: Path, label: str, routing: object) -> OutputHealthIssue | None:
    count_fields = (
        "eligible_count",
        "selected_count",
        "skipped_due_to_cap_count",
        "conflicted_count",
    )
    required = {"ensemble_enabled", *count_fields}
    if not isinstance(routing, dict) or not required.issubset(routing.keys()):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"routing missing ensemble_enabled/count fields for {label}",
        )
    if not isinstance(routing.get("ensemble_enabled"), bool):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"ensemble_enabled must be a boolean for {label}",
        )
    for field in count_fields:
        if not _is_non_negative_int(routing.get(field)):
            return OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                f"{field} must be a non-negative integer for {label}",
            )
    return None


def _validate_cost_log_budget_guard(path: Path, label: str, budget_guard: object) -> OutputHealthIssue | None:
    required = {
        "mode",
        "decision_counts",
        "guarded_paths",
        "profile_counts",
        "would_block_count",
        "blocked_count",
        "total_estimated_incremental_cost_usd",
    }
    if not isinstance(budget_guard, dict) or not required.issubset(budget_guard.keys()):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"budget_guard missing mode/count/path fields for {label}",
        )
    if not isinstance(budget_guard.get("mode"), str):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"mode must be a string for {label} budget_guard",
        )
    for field in ("decision_counts", "profile_counts"):
        if not _is_non_negative_int_mapping(budget_guard.get(field)):
            return OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                f"{field} must be an object with non-negative integer counts for {label} budget_guard",
            )
    if not _is_string_mapping(budget_guard.get("guarded_paths")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"guarded_paths must be an object with string values for {label} budget_guard",
        )
    for field in ("would_block_count", "blocked_count"):
        if not _is_non_negative_int(budget_guard.get(field)):
            return OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                f"{field} must be a non-negative integer for {label} budget_guard",
            )
    if not _is_non_negative_number(budget_guard.get("total_estimated_incremental_cost_usd")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"total_estimated_incremental_cost_usd must be a non-negative number for {label} budget_guard",
        )
    return None


def _validate_cost_log_deep_pass_value(path: Path, label: str, deep_pass_value: object) -> OutputHealthIssue | None:
    required = {
        "deep_cost_usd",
        "selected_ticker_count",
        "cost_per_selected_ticker_usd",
        "share_of_total_cost",
        "worth_it_hint",
    }
    if not isinstance(deep_pass_value, dict) or not required.issubset(deep_pass_value.keys()):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"deep_pass_value missing cost/count/share fields for {label}",
        )
    for field in ("deep_cost_usd", "cost_per_selected_ticker_usd"):
        if not _is_non_negative_number(deep_pass_value.get(field)):
            return OutputHealthIssue(
                "invalid_cost_log",
                str(path),
                f"{field} must be a non-negative number for {label} deep_pass_value",
            )
    if not _is_non_negative_int(deep_pass_value.get("selected_ticker_count")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"selected_ticker_count must be a non-negative integer for {label} deep_pass_value",
        )
    if not _is_probability(deep_pass_value.get("share_of_total_cost")):
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"share_of_total_cost must be a number from 0 to 1 for {label} deep_pass_value",
        )
    if not isinstance(deep_pass_value.get("worth_it_hint"), str) or not deep_pass_value.get("worth_it_hint", "").strip():
        return OutputHealthIssue(
            "invalid_cost_log",
            str(path),
            f"worth_it_hint must be a non-empty string for {label} deep_pass_value",
        )
    return None
