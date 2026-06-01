"""Health checks for latest-run routing outcome metadata."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_number,
    _is_number,
    _is_number_or_none,
    _is_string_list,
)


def _validate_routing_latest_run(path: Path, latest_run: dict) -> OutputHealthIssue | None:
    required = {
        "run_date",
        "trigger_range",
        "max_daily_ensemble",
        "portfolio_priority",
        "deep_pass_count",
        "tickers",
    }
    if not required.issubset(latest_run.keys()):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            "latest_run missing run_date/trigger_range/max_daily_ensemble/portfolio_priority/deep_pass_count/tickers",
        )
    if not isinstance(latest_run.get("run_date"), str):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            "run_date must be a string for latest_run",
        )
    trigger_range = latest_run.get("trigger_range")
    if not isinstance(trigger_range, list) or len(trigger_range) != 2 or not all(_is_number(item) for item in trigger_range):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            "trigger_range must be a two-number list for latest_run",
        )
    for field in ("max_daily_ensemble", "deep_pass_count"):
        if not _is_non_negative_int(latest_run.get(field)):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a non-negative integer for latest_run",
            )
    if not isinstance(latest_run.get("portfolio_priority"), bool):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            "portfolio_priority must be a boolean for latest_run",
        )
    for field in ("selected_tickers", "skipped_due_to_priority"):
        if field in latest_run and not _is_string_list(latest_run.get(field)):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a list of strings for latest_run",
            )

    budget = latest_run.get("router_budget_estimate")
    if budget is not None:
        if not isinstance(budget, dict):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                "router_budget_estimate must be an object for latest_run",
            )
        issue = _validate_routing_budget(path, budget)
        if issue is not None:
            return issue

    tickers = latest_run.get("tickers")
    if not isinstance(tickers, list):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            "tickers must be a list for latest_run",
        )
    for index, row in enumerate(tickers):
        issue = _validate_routing_ticker(path, index, row)
        if issue is not None:
            return issue
    return None


def _validate_routing_budget(path: Path, budget: dict) -> OutputHealthIssue | None:
    if "selected_count" in budget and not _is_non_negative_int(budget.get("selected_count")):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            "selected_count must be a non-negative integer for router_budget_estimate",
        )
    for field in ("estimated_incremental_cost_usd", "estimated_monthly_cost_usd"):
        if field in budget and not _is_non_negative_number(budget.get(field)):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a non-negative number for router_budget_estimate",
            )
    return None


def _validate_routing_ticker(path: Path, index: int, row: object) -> OutputHealthIssue | None:
    if not isinstance(row, dict):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            f"tickers item {index} must be an object for latest_run",
        )
    required = {"ticker", "selected_for_deep"}
    if not required.issubset(row.keys()):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            f"tickers item {index} missing ticker/selected_for_deep",
        )
    if not isinstance(row.get("ticker"), str) or not row.get("ticker", "").strip():
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            f"ticker must be a non-empty string for latest_run tickers item {index}",
        )
    if not isinstance(row.get("selected_for_deep"), bool):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            f"selected_for_deep must be a boolean for latest_run tickers item {index}",
        )
    for field in ("reason", "action"):
        if field in row and row.get(field) is not None and not isinstance(row.get(field), str):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a string or null for latest_run tickers item {index}",
            )
    for field in ("in_portfolio", "skipped_due_to_priority"):
        if field in row and not isinstance(row.get(field), bool):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a boolean for latest_run tickers item {index}",
            )
    for field in ("conviction", "router_priority_score"):
        if field in row and not _is_number_or_none(row.get(field)):
            return OutputHealthIssue(
                "invalid_routing_outcome",
                str(path),
                f"{field} must be a number or null for latest_run tickers item {index}",
            )
    if "router_reason_codes" in row and not _is_string_list(row.get("router_reason_codes")):
        return OutputHealthIssue(
            "invalid_routing_outcome",
            str(path),
            f"router_reason_codes must be a list of strings for latest_run tickers item {index}",
        )
    return None
