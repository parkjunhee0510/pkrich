from __future__ import annotations

from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding


SCHEMA: tuple[tuple[str, type], ...] = (
    ("payload.ticker", str),
    ("payload.summary", str),
    ("payload.key_news", list),
    ("payload.news_references", list),
    ("payload.date", str),
)


def _get(obj: dict, dotted: str) -> Any:
    cur: Any = obj
    for key in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


class O1SchemaCompliance(BaseCheck):
    check_id = "O1"
    dimension = "schema_compliance"

    def run(self, dataset: Any) -> CheckResult:
        violations: list[Finding] = []
        total = 0
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                for path, expected in SCHEMA:
                    total += 1
                    val = _get(record, path)
                    if val is None or not isinstance(val, expected):
                        violations.append(Finding(
                            ticker=ticker, date=d, jsonpath="$." + path,
                            detail={"expected": expected.__name__,
                                    "got": type(val).__name__},
                        ))
        rate = (len(violations) / total) if total else 0.0
        sev = "pass" if rate == 0 else "fail"
        return CheckResult(
            check_id="O1",
            severity=sev,
            pass_rate=1.0 - rate,
            findings=tuple(violations[:50]),
            metrics={"violation_rate": rate, "total_records": float(total)},
            recommendation=(
                "Re-run analyzer modules with strict response_schema validation; check llm_runtime."
                if sev != "pass" else None
            ),
        )
