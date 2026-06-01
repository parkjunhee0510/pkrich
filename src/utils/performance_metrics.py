"""Aggregate pipeline performance metrics from existing artifacts."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from src.output.schema import SCHEMA_VERSION


def build_performance_payloads(
    *,
    output_root: Path | None = None,
    logs_root: Path | None = None,
    run_date: date | None = None,
    monthly_budget_usd: float = 5.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = output_root or Path("output")
    data_dir = root / "data"
    as_of = (run_date or date.today()).isoformat()

    cost_log = _load_json(data_dir / "cost_log.json")
    quality = _load_json(data_dir / "analysis_quality.json")
    evidence = _load_json(data_dir / "search_evidence.json")
    signal_quality = _load_json(data_dir / "signal_quality.json")
    analysis_performance = _load_json(data_dir / "analysis_performance.json")
    json_health = _scan_json_health(data_dir)

    latest_cost = _dict(cost_log.get("latest"))
    latest_quality = _dict(quality.get("latest"))
    latest_run_date = str(latest_cost.get("run_date") or latest_quality.get("run_date") or "")
    status = "ok" if latest_run_date else "insufficient_data"
    if json_health["invalid_json_count"] > 0:
        status = "degraded"

    baseline = {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of,
        "status": status,
        "latest_run_date": latest_run_date,
        "monthly_budget_usd": monthly_budget_usd,
        "json_health": json_health,
        "cost": _build_cost_summary(latest_cost, monthly_budget_usd=monthly_budget_usd),
        "quality": _build_quality_summary(latest_quality),
        "evidence": _build_evidence_summary(evidence),
        "signals": _build_signal_summary(signal_quality),
        "p1_readiness": _build_p1_readiness(
            evidence=evidence,
            latest_cost=latest_cost,
            analysis_performance=analysis_performance,
            json_health=json_health,
        ),
    }
    trends = {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of,
        "monthly_budget_usd": monthly_budget_usd,
        "runs": _build_trend_runs(cost_log, quality),
    }
    return baseline, trends


def build_quality_reliability_loop_payload(
    *,
    baseline: dict[str, Any],
    trends: dict[str, Any],
) -> dict[str, Any]:
    json_health = _dict(baseline.get("json_health"))
    p1_tracks = _dict(_dict(baseline.get("p1_readiness")).get("tracks"))
    analysis_track = _dict(p1_tracks.get("analysis_performance"))
    provider_track = _dict(p1_tracks.get("search_evidence_provider"))
    budget_guard_track = _dict(p1_tracks.get("budget_guard"))
    output_schema_track = _dict(p1_tracks.get("output_schema"))
    cost = _dict(baseline.get("cost"))
    evidence = _dict(baseline.get("evidence"))
    quality = _dict(baseline.get("quality"))
    trend_runs = trends.get("runs") if isinstance(trends.get("runs"), list) else []

    artifact_reliability_status = _artifact_reliability_status(json_health)
    decision_quality_status = _decision_quality_status(analysis_track)
    evidence_status = _evidence_quality_status(evidence, provider_track)
    cost_status = _cost_telemetry_status(cost, baseline)
    warnings = _quality_reliability_warnings(
        artifact_reliability_status=artifact_reliability_status,
        decision_quality_status=decision_quality_status,
        evidence_status=evidence_status,
        cost_status=cost_status,
        json_health=json_health,
        evidence=evidence,
        provider_track=provider_track,
        budget_guard_track=budget_guard_track,
    )
    summary = {
        "decision_quality_status": decision_quality_status,
        "artifact_reliability_status": artifact_reliability_status,
        "evidence_status": evidence_status,
        "cost_status": cost_status,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": str(baseline.get("as_of") or trends.get("as_of") or ""),
        "status": _quality_reliability_status(summary),
        "summary": summary,
        "decision_quality": {
            "status": decision_quality_status,
            "sample_count": _safe_int(analysis_track.get("sample_count")),
            "completed_return_window_count": _safe_int(
                analysis_track.get("completed_return_window_count", 0) or 0
            ),
            "evaluated_signal_window_count": _safe_int(
                analysis_track.get("evaluated_signal_window_count", 0) or 0
            ),
            "populated_conviction_bucket_count": _safe_int(
                analysis_track.get("populated_conviction_bucket_count", 0) or 0
            ),
            "factor_count": _safe_int(analysis_track.get("factor_count")),
            "action_change_coverage_ratio": _safe_float(
                analysis_track.get("action_change_coverage_ratio", 0.0) or 0.0
            ),
            "loop_readiness_status": str(analysis_track.get("loop_readiness_status", "")),
            "hallucination_ratio": _safe_float(quality.get("hallucination_ratio")),
            "validation_failure_rate": _safe_float(
                quality.get("validation_failure_rate", 0.0) or 0.0
            ),
            "fact_warning_count": _safe_int(quality.get("fact_warning_count")),
            "consistency_warning_count": _safe_int(
                quality.get("consistency_warning_count", 0) or 0
            ),
        },
        "artifact_reliability": {
            "status": artifact_reliability_status,
            "json_health_status": str(json_health.get("status", "missing")),
            "invalid_json_count": _safe_int(json_health.get("invalid_json_count")),
            "issue_count": _list_count(json_health.get("issues")),
            "output_schema_status": str(output_schema_track.get("status", "")),
        },
        "evidence_quality": {
            "status": evidence_status,
            "ticker_count": _safe_int(evidence.get("ticker_count")),
            "covered_ticker_count": _safe_int(evidence.get("covered_ticker_count")),
            "coverage_ratio": _safe_float(evidence.get("coverage_ratio")),
            "candidate_ticker_count": _safe_int(evidence.get("candidate_ticker_count")),
            "searched_ticker_count": _safe_int(evidence.get("searched_ticker_count")),
            "status_counts": _int_dict(evidence.get("status_counts")),
            "priority_ticker_count": _non_negative_int(evidence.get("priority_ticker_count")),
            "priority_covered_ticker_count": _non_negative_int(
                evidence.get("priority_covered_ticker_count", 0) or 0
            ),
            "priority_coverage_ratio": _safe_float(
                evidence.get("priority_coverage_ratio", 0.0) or 0.0
            ),
            "priority_status_counts": _non_negative_int_dict(
                evidence.get("priority_status_counts")
            ),
            "priority_refresh_reasons": _non_negative_int_dict(
                evidence.get("priority_refresh_reasons")
            ),
            "priority_refresh_candidate_count": _non_negative_int(
                evidence.get("priority_refresh_candidate_count", 0) or 0
            ),
            "priority_provider_error_count": _non_negative_int(
                evidence.get("priority_provider_error_count", 0) or 0
            ),
            "priority_not_refreshed_count": _non_negative_int(
                evidence.get("priority_not_refreshed_count", 0) or 0
            ),
            "priority_no_evidence_count": _non_negative_int(
                evidence.get("priority_no_evidence_count", 0) or 0
            ),
            "provider_issue_status": str(provider_track.get("provider_issue_status", "")),
            "operational_issue_count": _safe_int(
                provider_track.get("operational_issue_count", 0) or 0
            ),
        },
        "cost_and_runtime": {
            "status": cost_status,
            "cost_policy": "report_only",
            "total_cost_usd": _safe_float(cost.get("total_cost_usd")),
            "estimated_monthly_cost_usd": _safe_float(
                cost.get("estimated_monthly_cost_usd", 0.0) or 0.0
            ),
            "llm_calls": _safe_int(cost.get("llm_calls")),
            "llm_calls_per_ticker": _safe_float(cost.get("llm_calls_per_ticker")),
            "budget_guard_would_block_count": _safe_int(
                cost.get("budget_guard_would_block_count", 0) or 0
            ),
            "budget_guard_blocked_count": _safe_int(
                cost.get("budget_guard_blocked_count", 0) or 0
            ),
            "budget_guard_status": str(budget_guard_track.get("status", "")),
            "budget_guard_mode": str(budget_guard_track.get("mode", "")),
        },
        "trend_inputs": {
            "run_count": len(trend_runs),
            "latest_run_date": _latest_trend_run_date(trend_runs),
        },
        "warnings": warnings,
    }


def _artifact_reliability_status(json_health: dict[str, Any]) -> str:
    invalid_json_count = _safe_int(json_health.get("invalid_json_count"))
    return "failed" if invalid_json_count > 0 else "ok"


def _decision_quality_status(analysis_track: dict[str, Any]) -> str:
    loop_status = str(analysis_track.get("loop_readiness_status", ""))
    sample_count = _safe_int(analysis_track.get("sample_count"))
    if loop_status == "ready_for_quality_review":
        return "ok"
    if sample_count > 0:
        return "partial"
    return "insufficient_data"


def _evidence_quality_status(
    evidence: dict[str, Any],
    provider_track: dict[str, Any],
) -> str:
    if not evidence:
        return "missing"
    operational_issue_count = _safe_int(provider_track.get("operational_issue_count"))
    if _is_normalized_empty_evidence(evidence):
        return "insufficient_data"
    coverage_ratio = evidence.get("coverage_ratio")
    if coverage_ratio is not None:
        coverage = _safe_float(coverage_ratio)
        if coverage >= 0.95 and operational_issue_count <= 0:
            return "ok"
        return "partial"
    if operational_issue_count > 0:
        return "partial"
    return "insufficient_data"


def _cost_telemetry_status(cost: dict[str, Any], baseline: dict[str, Any]) -> str:
    if not cost:
        return "missing"
    has_latest_run = bool(str(baseline.get("latest_run_date") or "").strip())
    if (
        _safe_float(cost.get("total_cost_usd")) == 0.0
        and _safe_int(cost.get("llm_calls")) == 0
        and not has_latest_run
    ):
        return "missing"
    return "reported"


def _is_normalized_empty_evidence(evidence: dict[str, Any]) -> bool:
    return (
        _safe_int(evidence.get("ticker_count")) == 0
        and _safe_int(evidence.get("candidate_ticker_count")) == 0
        and _safe_int(evidence.get("searched_ticker_count")) == 0
        and not _int_dict(evidence.get("status_counts"))
        and not str(evidence.get("provider") or "").strip()
    )


def _quality_reliability_status(summary: dict[str, str]) -> str:
    statuses = set(summary.values())
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    if "partial" in statuses or "missing" in statuses:
        return "partial"
    if "insufficient_data" in statuses:
        return "insufficient_data"
    return "ok"


def _quality_reliability_warnings(
    *,
    artifact_reliability_status: str,
    decision_quality_status: str,
    evidence_status: str,
    cost_status: str,
    json_health: dict[str, Any],
    evidence: dict[str, Any],
    provider_track: dict[str, Any],
    budget_guard_track: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if artifact_reliability_status == "failed" or _safe_int(
        json_health.get("invalid_json_count", 0) or 0
    ) > 0:
        warnings.append("invalid_json_detected")
    if decision_quality_status == "insufficient_data":
        warnings.append("decision_quality_insufficient_samples")
    if evidence_status in {"insufficient_data", "missing"}:
        warnings.append("evidence_quality_insufficient_data")
    provider_issue_status = str(provider_track.get("provider_issue_status", ""))
    operational_issue_count = _safe_int(provider_track.get("operational_issue_count"))
    if operational_issue_count > 0 or provider_issue_status not in {"", "clean"}:
        warnings.append("provider_issue_seen")
    if _safe_int(budget_guard_track.get("blocked_count")) > 0:
        warnings.append("budget_guard_enforced_block_seen")
    if cost_status == "missing":
        warnings.append("cost_telemetry_missing")
    priority_ticker_count = _non_negative_int(evidence.get("priority_ticker_count"))
    priority_covered_ticker_count = _non_negative_int(
        evidence.get("priority_covered_ticker_count")
    )
    priority_refresh_reasons = _non_negative_int_dict(evidence.get("priority_refresh_reasons"))
    if priority_ticker_count > 0 and priority_covered_ticker_count <= 0:
        warnings.append("priority_evidence_zero_coverage")
    if _non_negative_int(evidence.get("priority_not_refreshed_count")) > 0:
        warnings.append("priority_evidence_not_refreshed")
    if _non_negative_int(evidence.get("priority_provider_error_count")) > 0:
        warnings.append("priority_evidence_provider_error")
    if priority_refresh_reasons.get("stale_cache", 0) > 0:
        warnings.append("priority_evidence_stale_cache")
    return warnings


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _latest_trend_run_date(runs: list[Any]) -> str:
    run_dates = [str(_dict(run).get("run_date", "")) for run in runs]
    run_dates = [run_date for run_date in run_dates if run_date]
    return max(run_dates) if run_dates else ""


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, float) and not math.isfinite(value):
        return default
    try:
        return int(value or default)
    except (OverflowError, TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value or default)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _scan_json_health(data_dir: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if data_dir.exists():
        for path in sorted(data_dir.rglob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                issues.append(
                    {
                        "path": path.relative_to(data_dir).as_posix(),
                        "error": str(exc),
                    }
                )
    return {
        "status": "ok" if not issues else "invalid_json",
        "invalid_json_count": len(issues),
        "issues": issues[:50],
    }


def _build_cost_summary(
    latest: dict[str, Any],
    *,
    monthly_budget_usd: float,
) -> dict[str, Any]:
    profiles = _dict(latest.get("profiles"))
    routing = _dict(latest.get("routing"))
    budget_guard = _dict(latest.get("budget_guard"))
    llm_calls = sum(_safe_int(_dict(profile).get("calls")) for profile in profiles.values())
    total_cost = round(_safe_float(latest.get("total_cost_usd")), 8)
    estimated_monthly = round(total_cost * 22, 4)
    ticker_count = _safe_int(latest.get("watchlist_ticker_count"))
    if ticker_count <= 0:
        ticker_count = _safe_int(routing.get("eligible_count"))
    return {
        "total_cost_usd": total_cost,
        "estimated_monthly_cost_usd": estimated_monthly,
        "monthly_budget_usd": monthly_budget_usd,
        "budget_usage_ratio": round(estimated_monthly / monthly_budget_usd, 4)
        if monthly_budget_usd
        else 0.0,
        "llm_calls": llm_calls,
        "ticker_count_for_rate": ticker_count,
        "llm_calls_per_ticker": round(llm_calls / ticker_count, 3) if ticker_count else 0.0,
        "deep_selected_count": _safe_int(routing.get("selected_count")),
        "routing_conflicted_count": _safe_int(routing.get("conflicted_count")),
        "budget_guard_would_block_count": _safe_int(budget_guard.get("would_block_count")),
        "budget_guard_blocked_count": _safe_int(budget_guard.get("blocked_count")),
    }


def _build_quality_summary(latest: dict[str, Any]) -> dict[str, Any]:
    validated = _safe_int(latest.get("validated_ticker_count"))
    validation_failures = _safe_int(latest.get("validation_failure_count"))
    hallucinations = _safe_int(latest.get("hallucination_warning_count"))
    return {
        "validated_ticker_count": validated,
        "validation_failure_count": validation_failures,
        "validation_failure_rate": round(validation_failures / validated, 4) if validated else 0.0,
        "hallucination_warning_count": hallucinations,
        "hallucination_ratio": round(_safe_float(latest.get("hallucination_ratio")), 4),
        "fact_warning_count": _safe_int(latest.get("fact_warning_count")),
        "consistency_warning_count": _safe_int(latest.get("consistency_warning_count")),
    }


def _build_evidence_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    by_ticker = _dict(evidence.get("by_ticker"))
    run_summary = _dict(evidence.get("run_summary"))
    priority_tickers = _priority_tickers(run_summary, by_ticker)
    ticker_count = len(by_ticker)
    covered = 0
    priority_covered = 0
    coverage_scores: list[float] = []
    freshness_scores: list[float] = []
    derived_priority_status_counts: dict[str, int] = {}
    cache_age_hours: list[int] = []
    for value in by_ticker.values():
        item = _dict(value)
        evidence_count = _safe_int(item.get("evidence_count"))
        if evidence_count > 0:
            covered += 1
            cache_age_hours.append(_non_negative_int(item.get("cache_age_hours")))
        coverage_scores.append(_safe_float(item.get("coverage_score")))
        freshness_scores.append(_safe_float(item.get("freshness_score")))
    for ticker in priority_tickers:
        item = _dict(by_ticker.get(ticker))
        if _safe_int(item.get("evidence_count")) > 0:
            priority_covered += 1
        status = str(item.get("evidence_status") or "unknown")
        derived_priority_status_counts[status] = (
            derived_priority_status_counts.get(status, 0) + 1
        )
    if isinstance(run_summary.get("priority_status_counts"), dict):
        priority_status_counts = _non_negative_int_dict(
            run_summary.get("priority_status_counts")
        )
    else:
        priority_status_counts = derived_priority_status_counts
    candidate_ticker_count = _safe_int(run_summary.get("candidate_ticker_count"))
    cache_hit_count = _safe_int(run_summary.get("cache_hit_count"))
    stale_cache_hit_count = _safe_int(run_summary.get("stale_cache_hit_count"))
    priority_refresh_reasons = _non_negative_int_dict(
        run_summary.get("priority_refresh_reasons")
    )
    priority_not_refreshed_count = max(
        priority_status_counts.get("not_refreshed", 0),
        priority_refresh_reasons.get("not_refreshed", 0),
    )
    return {
        "provider": str(evidence.get("provider", "")),
        "ticker_count": ticker_count,
        "covered_ticker_count": covered,
        "coverage_ratio": round(covered / ticker_count, 4) if ticker_count else 0.0,
        "average_coverage_score": _avg(coverage_scores),
        "average_freshness_score": _avg(freshness_scores),
        "candidate_ticker_count": candidate_ticker_count,
        "searched_ticker_count": _safe_int(run_summary.get("searched_ticker_count")),
        "cache_ttl_hours": _safe_int(run_summary.get("cache_ttl_hours")),
        "cache_hit_count": cache_hit_count,
        "stale_cache_hit_count": stale_cache_hit_count,
        "cache_hit_ratio": round(cache_hit_count / candidate_ticker_count, 4)
        if candidate_ticker_count
        else 0.0,
        "stale_cache_hit_ratio": round(stale_cache_hit_count / cache_hit_count, 4)
        if cache_hit_count
        else 0.0,
        "average_cache_age_hours": _avg([_safe_float(age_hours) for age_hours in cache_age_hours]),
        "max_cache_age_hours": max(cache_age_hours) if cache_age_hours else 0,
        "provider_candidate_count": _safe_int(run_summary.get("provider_candidate_count")),
        "status_counts": _int_dict(run_summary.get("status_counts")),
        "priority_ticker_count": len(priority_tickers),
        "priority_covered_ticker_count": priority_covered,
        "priority_coverage_ratio": round(priority_covered / len(priority_tickers), 4)
        if priority_tickers
        else 0.0,
        "priority_status_counts": priority_status_counts,
        "priority_refresh_reasons": priority_refresh_reasons,
        "priority_refresh_candidate_count": _non_negative_int(
            run_summary.get("priority_refresh_candidate_count")
        ),
        "priority_provider_error_count": priority_status_counts.get("provider_error", 0),
        "priority_not_refreshed_count": priority_not_refreshed_count,
        "priority_no_evidence_count": priority_status_counts.get("no_evidence", 0),
    }


def _build_signal_summary(signal_quality: dict[str, Any]) -> dict[str, Any]:
    turnover = _dict(signal_quality.get("turnover"))
    kelly = _dict(signal_quality.get("kelly"))
    return {
        "turnover_status": str(turnover.get("status", "missing")),
        "avg_turnover": _safe_float(turnover.get("avg_turnover")),
        "kelly_status": str(kelly.get("status", "missing")),
    }


def _build_p1_readiness(
    *,
    evidence: dict[str, Any],
    latest_cost: dict[str, Any],
    analysis_performance: dict[str, Any],
    json_health: dict[str, Any],
) -> dict[str, Any]:
    tracks = {
        "search_evidence_provider": _build_p1_search_evidence_provider(evidence),
        "budget_guard": _build_p1_budget_guard(latest_cost),
        "analysis_performance": _build_p1_analysis_performance(analysis_performance),
        "output_schema": _build_p1_output_schema(json_health),
    }
    statuses = [str(_dict(track).get("status", "insufficient_data")) for track in tracks.values()]
    if any(status == "needs_attention" for status in statuses):
        status = "attention"
    elif any(status == "insufficient_data" for status in statuses):
        status = "insufficient_data"
    else:
        status = "ready"
    return {
        "status": status,
        "mode": "read_only_report",
        "tracks": tracks,
    }


def _build_p1_search_evidence_provider(evidence: dict[str, Any]) -> dict[str, Any]:
    run_summary = _dict(evidence.get("run_summary"))
    status_counts = _int_dict(run_summary.get("status_counts"))
    provider = str(evidence.get("provider", ""))
    candidate_ticker_count = _safe_int(run_summary.get("candidate_ticker_count"))
    provider_candidate_count = _safe_int(run_summary.get("provider_candidate_count"))
    priority_ticker_count = _non_negative_int(run_summary.get("priority_ticker_count"))
    searched_ticker_count = _safe_int(run_summary.get("searched_ticker_count"))
    cache_hit_count = _safe_int(run_summary.get("cache_hit_count"))
    stale_cache_hit_count = _safe_int(run_summary.get("stale_cache_hit_count"))
    provider_call_count = _safe_int(run_summary.get("provider_call_count"))
    provider_error_count = max(
        status_counts.get("provider_error", 0),
        _safe_int(run_summary.get("provider_error_count")),
    )
    provider_unavailable_count = status_counts.get("provider_unavailable", 0)
    cache_error_count = max(
        status_counts.get("cache_error", 0),
        _safe_int(run_summary.get("cache_error_count")),
    )
    skipped_ticker_count = _safe_int(run_summary.get("skipped_ticker_count"))

    if not provider or candidate_ticker_count <= 0:
        status = "insufficient_data"
    elif provider == "openai" and provider_error_count > 0:
        status = "needs_attention"
    elif provider == "openai":
        status = "live_provider_reviewed"
    else:
        status = "ready_for_limited_provider_validation"

    return {
        "status": status,
        "provider": provider,
        "candidate_ticker_count": candidate_ticker_count,
        "priority_ticker_count": priority_ticker_count,
        "searched_ticker_count": searched_ticker_count,
        "provider_candidate_count": provider_candidate_count,
        "provider_call_count": provider_call_count,
        "cache_hit_count": cache_hit_count,
        "stale_cache_hit_count": stale_cache_hit_count,
        "provider_error_count": provider_error_count,
        "provider_unavailable_count": provider_unavailable_count,
        "cache_error_count": cache_error_count,
        "skipped_ticker_count": skipped_ticker_count,
        "cap_review_status": _search_cap_review_status(
            provider=provider,
            provider_candidate_count=provider_candidate_count,
            priority_ticker_count=priority_ticker_count,
            candidate_ticker_count=candidate_ticker_count,
        ),
        "priority_refresh_candidate_ratio": round(
            provider_candidate_count / priority_ticker_count,
            4,
        )
        if priority_ticker_count
        else 0.0,
        "provider_issue_status": _search_provider_issue_status(
            provider_error_count=provider_error_count,
            provider_unavailable_count=provider_unavailable_count,
            cache_error_count=cache_error_count,
        ),
        "operational_issue_count": (
            provider_error_count + provider_unavailable_count + cache_error_count
        ),
        "stale_cache_reuse_status": "stale_cache_reused"
        if stale_cache_hit_count > 0
        else "no_stale_cache_reuse",
        "status_counts": status_counts,
    }


def _search_cap_review_status(
    *,
    provider: str,
    provider_candidate_count: int,
    priority_ticker_count: int,
    candidate_ticker_count: int,
) -> str:
    if provider == "cache" and provider_candidate_count <= 0:
        return "cache_only_default"
    if provider_candidate_count <= 0:
        return "no_provider_candidates"
    if priority_ticker_count > 0 and provider_candidate_count <= priority_ticker_count:
        return "priority_queued_within_cap"
    if provider_candidate_count <= candidate_ticker_count:
        return "candidate_cap_preserved"
    return "needs_attention"


def _search_provider_issue_status(
    *,
    provider_error_count: int,
    provider_unavailable_count: int,
    cache_error_count: int,
) -> str:
    if provider_error_count > 0:
        return "provider_error_seen"
    if cache_error_count > 0:
        return "cache_error_seen"
    if provider_unavailable_count > 0:
        return "provider_unavailable_seen"
    return "clean"


def _build_p1_budget_guard(latest_cost: dict[str, Any]) -> dict[str, Any]:
    budget_guard = _dict(latest_cost.get("budget_guard"))
    guarded_paths = _dict(budget_guard.get("guarded_paths"))
    decision_counts = _int_dict(budget_guard.get("decision_counts"))
    guarded_path_status_counts = _string_value_counts(guarded_paths)
    would_block_count = _safe_int(budget_guard.get("would_block_count"))
    blocked_count = _safe_int(budget_guard.get("blocked_count"))
    mode = str(budget_guard.get("mode", ""))
    if not budget_guard:
        status = "insufficient_data"
    elif blocked_count > 0:
        status = "enforce_active"
    elif would_block_count > 0:
        status = "report_ready"
    else:
        status = "shadow_observing"
    return {
        "status": status,
        "mode": mode,
        "enforce_review_status": _budget_guard_enforce_review_status(
            mode=mode,
            would_block_count=would_block_count,
            blocked_count=blocked_count,
            has_budget_guard=bool(budget_guard),
        ),
        "decision_counts": decision_counts,
        "guarded_path_status_counts": guarded_path_status_counts,
        "would_block_count": would_block_count,
        "blocked_count": blocked_count,
        "guarded_path_count": len(guarded_paths),
        "would_block_path_count": guarded_path_status_counts.get("would_block", 0),
        "blocked_path_count": guarded_path_status_counts.get("blocked", 0),
        "allow_path_count": guarded_path_status_counts.get("allow", 0),
        "total_estimated_incremental_cost_usd": round(
            _safe_float(budget_guard.get("total_estimated_incremental_cost_usd")),
            8,
        ),
    }


def _budget_guard_enforce_review_status(
    *,
    mode: str,
    would_block_count: int,
    blocked_count: int,
    has_budget_guard: bool,
) -> str:
    normalized_mode = mode.strip().lower()
    if not has_budget_guard:
        return "insufficient_data"
    if normalized_mode == "enforce" and blocked_count > 0:
        return "enforce_active"
    if normalized_mode == "enforce":
        return "enforce_observing"
    if normalized_mode == "shadow" and would_block_count > 0:
        return "report_only_review_required"
    if normalized_mode == "shadow":
        return "shadow_observing"
    if normalized_mode == "off":
        return "off"
    return "unknown_mode"


def _build_p1_analysis_performance(analysis_performance: dict[str, Any]) -> dict[str, Any]:
    summary = _dict(analysis_performance.get("summary"))
    completed_return_windows = _str_list(summary.get("completed_return_windows"))
    sample_count = _safe_int(summary.get("sample_count"))
    decision_count = _safe_int(summary.get("decision_count"))
    signal_performance = _dict(analysis_performance.get("signal_performance"))
    conviction_calibration = _dict(analysis_performance.get("conviction_calibration"))
    conviction_buckets = _dict(conviction_calibration.get("buckets"))
    regime_performance = _dict(analysis_performance.get("regime_performance"))
    factor_attribution = _dict(analysis_performance.get("factor_attribution"))
    factors = _dict(factor_attribution.get("factors"))
    action_change_reasons = analysis_performance.get("action_change_reasons")
    action_change_count = len(action_change_reasons) if isinstance(action_change_reasons, list) else 0
    evaluated_signal_window_count = _evaluated_signal_window_count(signal_performance)
    populated_conviction_bucket_count = _populated_conviction_bucket_count(conviction_buckets)
    factor_count = len(factors)
    if not summary:
        status = "insufficient_data"
    elif sample_count > 0 and completed_return_windows:
        status = "ready"
    else:
        status = "insufficient_data"
    return {
        "status": status,
        "mode": str(summary.get("mode", "")),
        "sample_count": sample_count,
        "decision_count": decision_count,
        "completed_return_windows": completed_return_windows,
        "completed_return_window_count": len(completed_return_windows),
        "evaluated_signal_window_count": evaluated_signal_window_count,
        "conviction_bucket_count": len(conviction_buckets),
        "populated_conviction_bucket_count": populated_conviction_bucket_count,
        "calibration_status": str(conviction_calibration.get("status") or "insufficient_data"),
        "regime_count": len(regime_performance),
        "factor_count": factor_count,
        "factor_attribution_status": str(factor_attribution.get("status") or "insufficient_data"),
        "missing_factor_sample_count": _safe_int(
            factor_attribution.get("missing_factor_sample_count", 0) or 0
        ),
        "action_change_reason_count": action_change_count,
        "action_change_coverage_ratio": round(
            min(action_change_count / decision_count, 1.0),
            4,
        )
        if decision_count
        else 0.0,
        "loop_readiness_status": _analysis_loop_readiness_status(
            sample_count=sample_count,
            completed_return_window_count=len(completed_return_windows),
            evaluated_signal_window_count=evaluated_signal_window_count,
            populated_conviction_bucket_count=populated_conviction_bucket_count,
            factor_count=factor_count,
        ),
    }


def _evaluated_signal_window_count(signal_performance: dict[str, Any]) -> int:
    count = 0
    for action_payload in signal_performance.values():
        action_windows = _dict(action_payload)
        for window_payload in action_windows.values():
            if _safe_int(_dict(window_payload).get("completed_count")) > 0:
                count += 1
    return count


def _populated_conviction_bucket_count(conviction_buckets: dict[str, Any]) -> int:
    count = 0
    for bucket_payload in conviction_buckets.values():
        if _safe_int(_dict(bucket_payload).get("sample_count")) > 0:
            count += 1
    return count


def _analysis_loop_readiness_status(
    *,
    sample_count: int,
    completed_return_window_count: int,
    evaluated_signal_window_count: int,
    populated_conviction_bucket_count: int,
    factor_count: int,
) -> str:
    if sample_count <= 0:
        return "needs_samples"
    if completed_return_window_count <= 0 or evaluated_signal_window_count <= 0:
        return "needs_completed_returns"
    if populated_conviction_bucket_count <= 0:
        return "needs_conviction_calibration"
    if factor_count <= 0:
        return "needs_factor_attribution"
    return "ready_for_quality_review"


def _build_p1_output_schema(json_health: dict[str, Any]) -> dict[str, Any]:
    invalid_json_count = _safe_int(json_health.get("invalid_json_count"))
    issues = json_health.get("issues")
    issue_count = len(issues) if isinstance(issues, list) else 0
    return {
        "status": "ready" if invalid_json_count == 0 else "needs_attention",
        "json_health_status": str(json_health.get("status", "unknown")),
        "invalid_json_count": invalid_json_count,
        "issue_count": issue_count,
    }


def _build_trend_runs(cost_log: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, Any]]:
    quality_by_date = {
        str(run.get("run_date", "")): _dict(run)
        for run in _list(quality.get("runs"))
        if isinstance(run, dict)
    }
    runs: list[dict[str, Any]] = []
    for raw_run in _list(cost_log.get("runs")):
        run = _dict(raw_run)
        run_date = str(run.get("run_date", ""))
        profiles = _dict(run.get("profiles"))
        routing = _dict(run.get("routing"))
        budget_guard = _dict(run.get("budget_guard"))
        llm_calls = sum(_safe_int(_dict(profile).get("calls")) for profile in profiles.values())
        quality_run = quality_by_date.get(run_date, {})
        runs.append(
            {
                "run_date": run_date,
                "success": bool(run.get("success", False)),
                "total_cost_usd": round(_safe_float(run.get("total_cost_usd")), 8),
                "llm_calls": llm_calls,
                "hallucination_ratio": round(
                    _safe_float(quality_run.get("hallucination_ratio")),
                    4,
                ),
                "validation_failure_count": _safe_int(
                    quality_run.get("validation_failure_count", 0) or 0
                ),
                "deep_selected_count": _safe_int(routing.get("selected_count")),
                "budget_guard_would_block_count": _safe_int(
                    budget_guard.get("would_block_count", 0) or 0
                ),
            }
        )
    runs.sort(key=lambda item: str(item.get("run_date", "")))
    return runs


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _priority_tickers(run_summary: dict[str, Any], by_ticker: dict[str, Any]) -> list[str]:
    raw_priority = run_summary.get("priority_tickers")
    if isinstance(raw_priority, list):
        return [str(ticker).strip().upper() for ticker in raw_priority if str(ticker).strip()]
    return [
        str(ticker)
        for ticker, summary in by_ticker.items()
        if _dict(summary).get("priority_for_refresh") is True
    ]


def _int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw_count in value.items():
        result[str(key)] = _safe_int(raw_count)
    return result


def _non_negative_int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw_count in value.items():
        result[str(key)] = _non_negative_int(raw_count)
    return result


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _string_value_counts(value: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_item in value.values():
        item = str(raw_item or "unknown").strip() or "unknown"
        counts[item] = counts.get(item, 0) + 1
    return counts


def _non_negative_int(value: Any) -> int:
    return max(0, _safe_int(value))
