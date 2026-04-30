from __future__ import annotations

from collections import Counter
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class R2RetryDistribution(BaseCheck):
    check_id = "R2"
    dimension = "retry_distribution"

    def run(self, dataset: Any) -> CheckResult:
        retry_counts: Counter[str] = Counter()
        for ev in dataset.logs:
            if ev.message == "retry" and ev.ticker:
                retry_counts[ev.ticker] += 1
        worst = max(retry_counts.values()) if retry_counts else 0
        worst_t = max(retry_counts, key=lambda k: retry_counts[k]) if retry_counts else None
        sev = severity_for("R2", value=worst, kind="retry_per_ticker")
        findings: list[Finding] = []
        if worst_t and sev != "pass":
            findings.append(Finding(
                ticker=worst_t, module="analyzer",
                detail={"retry_count_14d": retry_counts[worst_t]},
            ))
        return CheckResult(
            check_id="R2",
            severity=sev,
            pass_rate=1.0 if worst == 0 else max(0.0, 1.0 - worst / 14),
            findings=tuple(findings),
            metrics={"max_retry_per_ticker": float(worst),
                     "sample_count": float(len(dataset.logs)),
                     "tickers_with_retries": float(len(retry_counts))},
            recommendation=(
                f"Investigate {worst_t} retries; often indicates collector data shape regression."
                if sev != "pass" else None
            ),
        )
