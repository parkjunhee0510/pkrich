from __future__ import annotations

import statistics
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class I4InputSizeDrift(BaseCheck):
    check_id = "I4"
    dimension = "input_size_drift"

    def run(self, dataset: Any) -> CheckResult:
        per_ticker_tokens: dict[str, list[int]] = {t: [] for t in dataset.tickers}
        for d, summary in dataset.summaries.items():
            usage = (summary.get("model_usage") or {}).get("per_ticker_tokens") or {}
            for t in dataset.tickers:
                if t in usage:
                    per_ticker_tokens[t].append(int(usage[t]))
        cvs: dict[str, float] = {}
        findings: list[Finding] = []
        for t, samples in per_ticker_tokens.items():
            if len(samples) < 2:
                continue
            mean = statistics.fmean(samples)
            if mean == 0:
                continue
            stdev = statistics.pstdev(samples)
            cvs[t] = stdev / mean
        worst = max(cvs.values()) if cvs else 0.0
        worst_t = max(cvs, key=lambda k: cvs[k]) if cvs else None
        sev = severity_for("I4", value=worst, kind="cv")
        if worst_t and sev != "pass":
            findings.append(Finding(
                ticker=worst_t, module="prompt_tokens",
                detail={"cv": worst, "samples": per_ticker_tokens[worst_t]},
            ))
        return CheckResult(
            check_id="I4",
            severity=sev,
            pass_rate=1.0 - min(worst, 1.0),
            findings=tuple(findings),
            metrics={"worst_cv": worst, **{f"cv_{t}": v for t, v in cvs.items()}},
            recommendation=(
                f"{worst_t} prompt size CV {worst:.2f}; investigate news/filing volume swings."
                if sev != "pass" else None
            ),
        )
