"""Warning-level operational metrics for output health checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.output.health_common import OutputHealthIssue, _load_json_object


def collect_operational_metric_warnings(source_root: Path) -> tuple[OutputHealthIssue, ...]:
    warnings: list[OutputHealthIssue] = []
    warnings.extend(_cost_warnings(source_root))
    warnings.extend(_evidence_warnings(source_root))
    return tuple(warnings)


def _cost_warnings(source_root: Path) -> list[OutputHealthIssue]:
    warnings: list[OutputHealthIssue] = []
    cost_path = source_root / "cost_log.json"
    baseline_path = source_root / "performance_baseline.json"
    cost_log = _load_json_object(cost_path)
    baseline = _load_json_object(baseline_path)
    cost_summary = _dict(baseline.get("cost"))
    latest = _dict(cost_log.get("latest"))
    comparable = _previous_comparable_run(cost_log, latest)
    latest_cost = _float(latest.get("total_cost_usd"))
    previous_cost = _float(comparable.get("total_cost_usd"))
    if latest_cost > previous_cost > 0:
        delta = round(latest_cost - previous_cost, 8)
        pct = round(((latest_cost / previous_cost) - 1.0) * 100.0, 2)
        warnings.append(
            OutputHealthIssue(
                "cost_increased_vs_comparable_run",
                str(cost_path),
                _cost_increase_detail(
                    latest=latest,
                    comparable=comparable,
                    cost_summary=cost_summary,
                    delta=delta,
                    pct=pct,
                ),
            )
        )

    budget_usage = _float(cost_summary.get("budget_usage_ratio"))
    if budget_usage > 1.0:
        warnings.append(
            OutputHealthIssue(
                "cost_budget_over_target",
                str(baseline_path),
                f"budget_usage_ratio={round(budget_usage, 4)}",
            )
        )

    budget_guard = _dict(latest.get("budget_guard"))
    would_block = _int(budget_guard.get("would_block_count"))
    if would_block > 0:
        warnings.append(
            OutputHealthIssue(
                "budget_guard_would_block",
                str(cost_path),
                f"would_block_count={would_block} mode={budget_guard.get('mode', '')}",
            )
        )
    return warnings


def _evidence_warnings(source_root: Path) -> list[OutputHealthIssue]:
    warnings: list[OutputHealthIssue] = []
    path = source_root / "search_evidence.json"
    payload = _load_json_object(path)
    run_summary = _dict(payload.get("run_summary"))
    status_counts = _dict(run_summary.get("status_counts"))
    priority_status_counts = _dict(run_summary.get("priority_status_counts"))
    provider_errors = max(
        _int(run_summary.get("provider_error_count")),
        _int(status_counts.get("provider_error")),
        _int(priority_status_counts.get("provider_error")),
        _ticker_status_count(payload, "evidence_status", "provider_error"),
        _ticker_status_count(payload, "provider_status", "provider_error"),
    )
    if provider_errors > 0:
        warnings.append(
            OutputHealthIssue(
                "evidence_provider_error",
                str(path),
                (
                    f"provider_error_count={provider_errors} "
                    f"status_counts={status_counts} priority_status_counts={priority_status_counts}"
                ),
            )
        )

    priority_count = _int(run_summary.get("priority_ticker_count"))
    covered = _int(priority_status_counts.get("covered"))
    if priority_count > 0 and covered == 0:
        warnings.append(
            OutputHealthIssue(
                "priority_evidence_zero_coverage",
                str(path),
                f"priority_ticker_count={priority_count} priority_status_counts={priority_status_counts}",
            )
        )
    return warnings


def _cost_increase_detail(
    *,
    latest: dict[str, Any],
    comparable: dict[str, Any],
    cost_summary: dict[str, Any],
    delta: float,
    pct: float,
) -> str:
    return (
        f"latest={latest.get('run_date')} comparable={comparable.get('run_date')} "
        f"delta={delta} pct={pct} profiles={_profile_deltas(latest, comparable)} "
        f"routing={_routing_delta(latest, comparable)} "
        f"llm_calls_per_ticker={_round_float(cost_summary.get('llm_calls_per_ticker'))} "
        f"estimated_monthly_cost_usd={_round_float(cost_summary.get('estimated_monthly_cost_usd'))} "
        f"budget_usage_ratio={_round_float(cost_summary.get('budget_usage_ratio'))} "
        f"output_tokens_delta=unavailable"
    )


def _profile_deltas(latest: dict[str, Any], comparable: dict[str, Any]) -> dict[str, dict[str, float | int | str]]:
    latest_profiles = _dict(latest.get("profiles"))
    comparable_profiles = _dict(comparable.get("profiles"))
    result: dict[str, dict[str, float | int | str]] = {}
    for profile_name in ("economy", "standard", "deep"):
        current = _dict(latest_profiles.get(profile_name))
        previous = _dict(comparable_profiles.get(profile_name))
        result[profile_name] = {
            "calls_delta": _int(current.get("calls")) - _int(previous.get("calls")),
            "tokens_delta": _int(current.get("tokens")) - _int(previous.get("tokens")),
            "input_tokens_delta": _int(current.get("input_tokens")) - _int(previous.get("input_tokens")),
            "cached_input_tokens_delta": _int(current.get("cached_input_tokens"))
            - _int(previous.get("cached_input_tokens")),
            "cost_delta": _round_float(_float(current.get("cost_usd")) - _float(previous.get("cost_usd"))),
            "output_tokens_delta": _numeric_delta_or_unavailable(current, previous, "output_tokens"),
        }
    return result


def _routing_delta(latest: dict[str, Any], comparable: dict[str, Any]) -> dict[str, int]:
    current = _dict(latest.get("routing"))
    previous = _dict(comparable.get("routing"))
    fields = ("eligible_count", "selected_count", "skipped_due_to_cap_count", "conflicted_count")
    result: dict[str, int] = {}
    for field in fields:
        result[field] = _int(current.get(field))
        result[f"{field}_delta"] = _int(current.get(field)) - _int(previous.get(field))
    return result


def _previous_comparable_run(cost_log: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    runs = cost_log.get("runs")
    if not isinstance(runs, list):
        return {}
    latest_date = latest.get("run_date")
    latest_eligible = _int(_dict(latest.get("routing")).get("eligible_count"))
    successful = [
        _dict(row)
        for row in runs
        if isinstance(row, dict) and row.get("success") is True and row.get("run_date") != latest_date
    ]
    if latest_eligible > 0:
        for row in successful:
            if _int(_dict(row.get("routing")).get("eligible_count")) == latest_eligible:
                return row
    return successful[0] if successful else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _numeric_delta_or_unavailable(current: dict[str, Any], previous: dict[str, Any], field: str) -> float | int | str:
    if field not in current and field not in previous:
        return "unavailable"
    if isinstance(current.get(field), int) and isinstance(previous.get(field), int):
        return _int(current.get(field)) - _int(previous.get(field))
    return _round_float(_float(current.get(field)) - _float(previous.get(field)))


def _round_float(value: Any) -> float:
    return round(_float(value), 8)


def _ticker_status_count(payload: dict[str, Any], field: str, expected: str) -> int:
    count = 0
    by_ticker = payload.get("by_ticker")
    if not isinstance(by_ticker, dict):
        return count
    for summary in by_ticker.values():
        if isinstance(summary, dict) and summary.get(field) == expected:
            count += 1
    return count


def _float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
