from __future__ import annotations

import re
import statistics
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


HANGUL_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")


def _korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    han = len(HANGUL_RE.findall(text))
    lat = len(LATIN_RE.findall(text))
    denom = han + lat
    return (han / denom) if denom else 0.0


class O4LanguageConsistency(BaseCheck):
    check_id = "O4"
    dimension = "language_consistency"

    def run(self, dataset: Any) -> CheckResult:
        per_ticker_stds: dict[str, float] = {}
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            ratios = [
                _korean_ratio((record.get("payload") or {}).get("summary") or "")
                for record in days.values()
            ]
            if len(ratios) < 2:
                continue
            std = statistics.pstdev(ratios)
            per_ticker_stds[ticker] = std
            if std > 0.30:
                findings.append(Finding(
                    ticker=ticker, jsonpath="$.payload.summary",
                    detail={"korean_ratio_std": std, "samples": ratios},
                ))
        worst = max(per_ticker_stds.values()) if per_ticker_stds else 0.0
        sev = severity_for("O4", value=worst, kind="lang_ratio_std")
        return CheckResult(
            check_id="O4",
            severity=sev,
            pass_rate=1.0 - min(worst, 1.0),
            findings=tuple(findings),
            metrics={"worst_korean_ratio_std": worst},
            recommendation=(
                "Pin language in system prompt; reject mixed-language outputs in llm_runtime parser."
                if sev != "pass" else None
            ),
        )
