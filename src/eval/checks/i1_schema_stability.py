from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = (
    "ticker", "summary", "key_news", "news_references", "date",
)


class I1SchemaStability(BaseCheck):
    check_id = "I1"
    dimension = "schema_stability"

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        missing = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                for f in REQUIRED_PAYLOAD_FIELDS:
                    total += 1
                    if f not in payload:
                        missing += 1
                        findings.append(Finding(
                            ticker=ticker, date=d, module="payload",
                            jsonpath=f"$.payload.{f}",
                            detail={"reason": "missing_required_field"},
                        ))
        rate = (missing / total) if total else 0.0
        sev = severity_for("I1", value=rate, kind="missing_field_rate")
        recommendation = None
        if sev != "pass":
            recommendation = "Inspect collector/analyzer normalization for dropped fields."
        return CheckResult(
            check_id="I1",
            severity=sev,
            pass_rate=1.0 - rate,
            findings=tuple(findings[:50]),
            metrics={"missing_field_rate": rate, "total_records": float(total)},
            recommendation=recommendation,
        )
