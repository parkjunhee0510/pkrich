"""Write performance baseline, trends, and report artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from src.output.json_export import _sync_web_public_data
from src.output.json_writer import write_json_file
from src.utils.performance_metrics import (
    build_performance_payloads,
    build_quality_reliability_loop_payload,
)
from src.utils.model_config import load_budget_guard_config


def write_performance_outputs(
    *,
    output_root: Path | None = None,
    logs_root: Path | None = None,
    project_root: Path | None = None,
    run_date: date | None = None,
    monthly_budget_usd: float | None = None,
) -> dict[str, Path]:
    root = output_root or Path("output")
    project = project_root or root.parent
    effective_monthly_budget_usd = (
        monthly_budget_usd
        if monthly_budget_usd is not None
        else _default_monthly_budget_usd(project)
    )
    data_dir = root / "data"
    baseline, trends = build_performance_payloads(
        output_root=root,
        logs_root=logs_root,
        run_date=run_date,
        monthly_budget_usd=effective_monthly_budget_usd,
    )
    quality_loop = build_quality_reliability_loop_payload(
        baseline=baseline,
        trends=trends,
    )

    baseline_path = data_dir / "performance_baseline.json"
    trends_path = data_dir / "performance_trends.json"
    quality_loop_path = data_dir / "quality_reliability_loop.json"
    write_json_file(baseline_path, baseline)
    write_json_file(trends_path, trends)
    write_json_file(quality_loop_path, quality_loop)
    report_path = _write_performance_report(
        project,
        baseline,
        trends,
        quality_loop,
        run_date=run_date,
    )
    _sync_web_public_data(data_dir, project)
    return {
        "baseline_path": baseline_path,
        "trends_path": trends_path,
        "quality_loop_path": quality_loop_path,
        "report_path": report_path,
    }


def _default_monthly_budget_usd(project_root: Path) -> float:
    config = load_budget_guard_config(str(project_root / "config" / "models.yaml"))
    return float(config.monthly_cap_usd)


def _write_performance_report(
    project_root: Path,
    baseline: dict[str, Any],
    trends: dict[str, Any],
    quality_loop: dict[str, Any],
    *,
    run_date: date | None,
) -> Path:
    report_date = (run_date or date.today()).isoformat()
    reports_dir = project_root / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"performance-{report_date}.md"
    cost = _dict(baseline.get("cost"))
    quality = _dict(baseline.get("quality"))
    evidence = _dict(baseline.get("evidence"))
    json_health = _dict(baseline.get("json_health"))
    p1_readiness = _dict(baseline.get("p1_readiness"))
    p1_tracks = _dict(p1_readiness.get("tracks"))
    p1_search = _dict(p1_tracks.get("search_evidence_provider"))
    p1_budget_guard = _dict(p1_tracks.get("budget_guard"))
    p1_analysis = _dict(p1_tracks.get("analysis_performance"))
    p1_output_schema = _dict(p1_tracks.get("output_schema"))
    quality_loop_summary = _dict(quality_loop.get("summary"))
    quality_loop_decision = _dict(quality_loop.get("decision_quality"))
    quality_loop_artifacts = _dict(quality_loop.get("artifact_reliability"))
    quality_loop_evidence = _dict(quality_loop.get("evidence_quality"))
    quality_loop_cost = _dict(quality_loop.get("cost_and_runtime"))
    lines = [
        f"# Performance Report {report_date}",
        "",
        "## Status",
        "",
        f"- Status: `{baseline.get('status', 'unknown')}`",
        f"- Latest run: `{baseline.get('latest_run_date', '')}`",
        f"- Invalid JSON files: `{json_health.get('invalid_json_count', 0)}`",
        "",
        "## Cost",
        "",
        f"- Total cost: `${cost.get('total_cost_usd', 0.0)}`",
        f"- Estimated monthly cost: `${cost.get('estimated_monthly_cost_usd', 0.0)}`",
        f"- LLM calls: `{cost.get('llm_calls', 0)}`",
        f"- LLM calls per ticker: `{cost.get('llm_calls_per_ticker', 0.0)}`",
        "",
        "## Quality",
        "",
        f"- Hallucination ratio: `{quality.get('hallucination_ratio', 0.0)}`",
        f"- Validation failure rate: `{quality.get('validation_failure_rate', 0.0)}`",
        "",
        "## Evidence",
        "",
        f"- Evidence coverage ratio: `{evidence.get('coverage_ratio', 0.0)}`",
        f"- Covered tickers: `{evidence.get('covered_ticker_count', 0)}`",
        f"- Priority evidence coverage: `{evidence.get('priority_coverage_ratio', 0.0)}`",
        f"- Priority evidence statuses: `{_format_counts(_dict(evidence.get('priority_status_counts')))}`",
        f"- Evidence cache hit ratio: `{evidence.get('cache_hit_ratio', 0.0)}`",
        f"- Stale cache hits: `{evidence.get('stale_cache_hit_count', 0)}/{evidence.get('cache_hit_count', 0)}`",
        f"- Average cache age hours: `{evidence.get('average_cache_age_hours', 0.0)}`",
        "",
        "## P1 Readiness",
        "",
        f"- Overall status: `{p1_readiness.get('status', 'unknown')}`",
        f"- Search evidence provider: `{p1_search.get('status', 'unknown')}`",
        f"- Search provider cap: `{p1_search.get('cap_review_status', 'unknown')}`",
        f"- Search provider issues: `{p1_search.get('provider_issue_status', 'unknown')}`",
        f"- Search provider calls: `{p1_search.get('provider_call_count', 0)}`",
        f"- Search stale cache: `{p1_search.get('stale_cache_reuse_status', 'unknown')}`",
        f"- BudgetGuard: `{p1_budget_guard.get('status', 'unknown')}`",
        f"- BudgetGuard review: `{p1_budget_guard.get('enforce_review_status', 'unknown')}`",
        f"- BudgetGuard would-block paths: `{p1_budget_guard.get('would_block_path_count', 0)}/{p1_budget_guard.get('guarded_path_count', 0)}`",
        f"- BudgetGuard blocked paths: `{p1_budget_guard.get('blocked_path_count', 0)}`",
        f"- BudgetGuard estimated incremental cost: `${p1_budget_guard.get('total_estimated_incremental_cost_usd', 0.0)}`",
        f"- Analysis performance: `{p1_analysis.get('status', 'unknown')}`",
        f"- Analysis loop: `{p1_analysis.get('loop_readiness_status', 'unknown')}`",
        f"- Analysis completed windows: `{p1_analysis.get('completed_return_window_count', 0)}`",
        f"- Analysis evaluated signal windows: `{p1_analysis.get('evaluated_signal_window_count', 0)}`",
        f"- Analysis factors tracked: `{p1_analysis.get('factor_count', 0)}`",
        f"- Analysis action-change coverage: `{p1_analysis.get('action_change_coverage_ratio', 0.0)}`",
        f"- Output schema: `{p1_output_schema.get('status', 'unknown')}`",
        "",
        "## Quality Reliability Loop",
        "",
        f"- Quality loop status: `{quality_loop.get('status', 'unknown')}`",
        f"- Decision quality status: `{quality_loop_summary.get('decision_quality_status', 'unknown')}`",
        f"- Artifact reliability status: `{quality_loop_summary.get('artifact_reliability_status', 'unknown')}`",
        f"- Evidence status: `{quality_loop_summary.get('evidence_status', 'unknown')}`",
        f"- Cost status: `{quality_loop_summary.get('cost_status', 'unknown')}`",
        f"- Decision sample count: `{quality_loop_decision.get('sample_count', 0)}`",
        f"- Completed return windows: `{quality_loop_decision.get('completed_return_window_count', 0)}`",
        f"- Evaluated signal windows: `{quality_loop_decision.get('evaluated_signal_window_count', 0)}`",
        f"- Populated conviction buckets: `{quality_loop_decision.get('populated_conviction_bucket_count', 0)}`",
        f"- Invalid JSON files: `{quality_loop_artifacts.get('invalid_json_count', 0)}`",
        f"- Evidence coverage: `{quality_loop_evidence.get('coverage_ratio', 0.0)}`",
        f"- Priority evidence coverage: `{quality_loop_evidence.get('priority_coverage_ratio', 0.0)}`",
        f"- Cost policy: `{quality_loop_cost.get('cost_policy', 'unknown')}`",
        "",
        "## Trend Rows",
        "",
        f"- Runs included: `{len(trends.get('runs', []))}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _format_counts(counts: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(counts):
        parts.append(f"{key}={counts[key]}")
    return ", ".join(parts)
