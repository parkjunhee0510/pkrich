from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class R1PipelineSummary(BaseCheck):
    check_id = "R1"
    dimension = "pipeline_summary"

    def run(self, dataset: Any) -> CheckResult:
        total_fallbacks = 0
        total_records = 0
        cost_series: list[float] = []
        for d, s in dataset.summaries.items():
            fallbacks = int(s.get("fallback_count") or 0)
            ticker_count = max(len(dataset.tickers), 1)
            total_fallbacks += fallbacks
            total_records += ticker_count
            cost_series.append(float(s.get("daily_api_cost_usd") or 0.0))
        rate = (total_fallbacks / total_records) if total_records else 0.0
        sev = severity_for("R1", value=rate, kind="fallback_rate")
        findings: list[Finding] = []
        if sev != "pass":
            findings.append(Finding(
                module="pipeline_summary",
                detail={"fallback_rate": rate, "total_fallbacks": total_fallbacks,
                        "cost_trend": cost_series},
            ))
        return CheckResult(
            check_id="R1",
            severity=sev,
            pass_rate=1.0 - min(rate, 1.0),
            findings=tuple(findings),
            metrics={"fallback_rate": rate,
                     "sample_count": float(len(dataset.summaries)),
                     "total_daily_cost_usd": sum(cost_series)},
            recommendation=(
                "Inspect retry logic in llm_runtime; high fallback often = schema parse failures."
                if sev != "pass" else None
            ),
        )
