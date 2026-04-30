from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


TRACKED_FIELDS: tuple[str, ...] = ("summary", "key_news", "news_references")
WHITELIST_OPTIONAL: tuple[str, ...] = ("options", "insider", "fundamentals")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, str)) and len(value) == 0:
        return True
    return False


class I2Missingness(BaseCheck):
    check_id = "I2"
    dimension = "missingness"

    def run(self, dataset: Any) -> CheckResult:
        per_field_total: dict[str, int] = {f: 0 for f in TRACKED_FIELDS}
        per_field_missing: dict[str, int] = {f: 0 for f in TRACKED_FIELDS}
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                for f in TRACKED_FIELDS:
                    per_field_total[f] += 1
                    if _is_missing(payload.get(f)):
                        per_field_missing[f] += 1
                        findings.append(Finding(
                            ticker=ticker, date=d, module="payload",
                            jsonpath=f"$.payload.{f}",
                            detail={"reason": "empty_or_none"},
                        ))
        rates = {
            f: (per_field_missing[f] / per_field_total[f]) if per_field_total[f] else 0.0
            for f in TRACKED_FIELDS
        }
        worst_rate = max(rates.values()) if rates else 0.0
        sev = severity_for("I2", value=worst_rate, kind="missingness_rate")
        worst_field = max(rates, key=lambda k: rates[k]) if rates else "-"
        return CheckResult(
            check_id="I2",
            severity=sev,
            pass_rate=1.0 - worst_rate,
            findings=tuple(findings[:50]),
            metrics={"worst_field_missing_rate": worst_rate,
                     "sample_count": float(sum(per_field_total.values())),
                     **{f"rate_{k}": v for k, v in rates.items()}},
            recommendation=(
                f"{worst_field} missingness {worst_rate:.0%}; review collector for that field."
                if sev != "pass" else None
            ),
        )
