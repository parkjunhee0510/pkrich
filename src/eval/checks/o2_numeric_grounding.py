from __future__ import annotations

import re
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


NUM_USD = re.compile(r"(\d+(?:\.\d+)?)\s*USD")
NUM_PCT = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
TOLERANCE_REL = 0.005


def _close(actual: float, claimed: float, rel: float = TOLERANCE_REL) -> bool:
    if actual == 0:
        return abs(claimed) < 1e-6
    return abs(actual - claimed) / abs(actual) <= rel


class O2NumericGrounding(BaseCheck):
    check_id = "O2"
    dimension = "numeric_grounding"

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        matched = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                summary = payload.get("summary") or ""
                metrics = payload.get("metrics") or {}
                price_actual = metrics.get("price")
                pct_actual = metrics.get("pct_change")

                for m in NUM_USD.finditer(summary):
                    total += 1
                    if price_actual is not None and _close(float(price_actual), float(m.group(1))):
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.summary",
                            detail={"claimed_usd": m.group(1), "actual_price": price_actual},
                        ))
                for m in NUM_PCT.finditer(summary):
                    total += 1
                    if pct_actual is not None and _close(float(pct_actual), float(m.group(1))):
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.summary",
                            detail={"claimed_pct": m.group(1), "actual_pct": pct_actual},
                        ))

        rate = (matched / total) if total else 1.0
        sev = severity_for("O2", value=rate, kind="match_rate")
        return CheckResult(
            check_id="O2",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"match_rate": rate, "total_numeric_claims": float(total)},
            recommendation=(
                "Anchor research_note prompt to actual price/% from collected data; "
                "consider passing metrics dict explicitly into the prompt."
                if sev != "pass" else None
            ),
        )
