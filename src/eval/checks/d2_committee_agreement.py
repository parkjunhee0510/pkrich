from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


class D2CommitteeAgreement(BaseCheck):
    check_id = "D2"
    dimension = "committee_agreement"

    def run(self, dataset: Any) -> CheckResult:
        per_key: dict[tuple, dict[str, str]] = defaultdict(dict)
        for ev in dataset.logs:
            if ev.component != "committee":
                continue
            role = (ev.detail or {}).get("role")
            action = (ev.detail or {}).get("action")
            if not role or not action or not ev.ticker:
                continue
            per_key[(ev.ticker, ev.date)][role] = action
        total = 0
        agreed = 0
        findings: list[Finding] = []
        for (ticker, d), roles in per_key.items():
            if len(roles) < 2:
                continue
            total += 1
            actions = set(roles.values())
            if len(actions) == 1:
                agreed += 1
            else:
                findings.append(Finding(
                    ticker=ticker, date=d, module="committee",
                    detail={"roles": dict(roles)},
                ))
        rate = (agreed / total) if total else 1.0
        sev = severity_for("D2", value=rate, kind="role_agreement")
        return CheckResult(
            check_id="D2",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"role_agreement": rate, "evaluated_decisions": float(total)},
            recommendation=(
                "Tighten committee aggregator: surface disagreements to the user instead of hiding them."
                if sev != "pass" else None
            ),
        )
