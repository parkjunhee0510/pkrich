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


def _parse_number(value: Any) -> float | None:
    match = re.search(r"[+-]?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _walk_values(obj: Any):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_values(value)
    else:
        yield obj


def _grounded_values(payload: dict[str, Any]) -> tuple[list[float], list[float]]:
    metrics = payload.get("metrics") or {}
    usd_values: list[float] = []
    pct_values: list[float] = []
    if metrics.get("price") is not None:
        usd_values.append(float(metrics["price"]))
    if metrics.get("pct_change") is not None:
        pct_values.append(float(metrics["pct_change"]))
    grounding_payload = {k: v for k, v in payload.items() if k != "summary"}
    for value in _walk_values(grounding_payload):
        text = str(value or "")
        if "USD" in text:
            parsed = _parse_number(text)
            if parsed is not None:
                usd_values.append(parsed)
        if "%" in text:
            parsed = _parse_number(text)
            if parsed is not None:
                pct_values.append(parsed)
    return usd_values, pct_values


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
                usd_values, pct_values = _grounded_values(payload)

                for m in NUM_USD.finditer(summary):
                    total += 1
                    claimed = float(m.group(1))
                    if any(_close(actual, claimed) for actual in usd_values):
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.summary",
                            detail={"claimed_usd": m.group(1), "grounded_usd_values": usd_values[:20]},
                        ))
                for m in NUM_PCT.finditer(summary):
                    total += 1
                    claimed = float(m.group(1))
                    if any(_close(actual, claimed) for actual in pct_values):
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.summary",
                            detail={"claimed_pct": m.group(1), "grounded_pct_values": pct_values[:20]},
                        ))

        rate = (matched / total) if total else 1.0
        if total == 0:
            return CheckResult(
                check_id="O2",
                severity="info",
                pass_rate=0.0,
                findings=(Finding(
                    module="payload",
                    jsonpath="$.payload.summary",
                    detail={"reason": "no_numeric_claims_evaluated"},
                ),),
                metrics={"match_rate": 0.0, "total_numeric_claims": 0.0, "sample_count": 0.0},
                recommendation="No numeric claims were available to evaluate; treat this as insufficient audit evidence.",
            )
        sev = severity_for("O2", value=rate, kind="match_rate")
        return CheckResult(
            check_id="O2",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"match_rate": rate, "total_numeric_claims": float(total), "sample_count": float(total)},
            recommendation=(
                "Anchor research_note prompt to actual price/% from collected data; "
                "consider passing metrics dict explicitly into the prompt."
                if sev != "pass" else None
            ),
        )
