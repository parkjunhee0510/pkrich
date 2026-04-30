from __future__ import annotations

from typing import Any, Literal

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


Direction = Literal["positive", "negative", "neutral"]

POS_LEX: tuple[str, ...] = ("긍정", "매수", "상승", "강세", "낙관", "positive", "buy", "bullish", "strong")
NEG_LEX: tuple[str, ...] = ("부정", "매도", "하락", "약세", "비관", "negative", "sell", "bearish", "weak")


def _direction_from_text(text: str) -> Direction:
    t = text.lower()
    pos = sum(1 for w in POS_LEX if w in t)
    neg = sum(1 for w in NEG_LEX if w in t)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _direction_from_severity(sev: str) -> Direction:
    s = (sev or "").lower()
    if s in ("low", "low risk"):
        return "positive"
    if s in ("high", "severe", "elevated"):
        return "negative"
    return "neutral"


def _direction_from_outlook(outlook: str) -> Direction:
    o = (outlook or "").lower()
    if o in ("positive", "bullish", "constructive"):
        return "positive"
    if o in ("negative", "bearish", "cautious"):
        return "negative"
    return "neutral"


class O5Contradiction(BaseCheck):
    check_id = "O5"
    dimension = "contradiction"

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        agreed = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                if "risk_assessment" not in payload or "research_narrative" not in payload:
                    continue
                total += 1
                a = _direction_from_text(payload.get("summary") or "")
                b = _direction_from_severity(
                    (payload.get("risk_assessment") or {}).get("severity") or "")
                c = _direction_from_outlook(
                    (payload.get("research_narrative") or {}).get("outlook") or "")
                directions = {a, b, c}
                if len(directions - {"neutral"}) <= 1:
                    agreed += 1
                else:
                    findings.append(Finding(
                        ticker=ticker, date=d, jsonpath="$.payload",
                        detail={"summary_dir": a, "risk_dir": b, "narrative_dir": c},
                    ))
        rate = (agreed / total) if total else 1.0
        if total == 0:
            return CheckResult(
                check_id="O5",
                severity="info",
                pass_rate=0.0,
                findings=(Finding(
                    module="payload",
                    jsonpath="$.payload",
                    detail={"reason": "no_contradiction_records_evaluated"},
                ),),
                metrics={"three_way_agreement": 0.0, "evaluated_records": 0.0, "sample_count": 0.0},
                recommendation="No payloads contained risk_assessment and research_narrative fields for contradiction checking.",
            )
        sev = severity_for("O5", value=rate, kind="three_way_agreement")
        return CheckResult(
            check_id="O5",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"three_way_agreement": rate, "evaluated_records": float(total), "sample_count": float(total)},
            recommendation=(
                "Add a coherence pass that vetoes mismatched summary/risk/outlook tuples."
                if sev != "pass" else None
            ),
        )
