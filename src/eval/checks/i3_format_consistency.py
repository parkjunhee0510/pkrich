from __future__ import annotations

import re
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$")
RFC822 = re.compile(r"^[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2} \d{4}")
SLASHED = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def _classify(s: str) -> str:
    if ISO_DATE.match(s):
        return "ISO-8601"
    if RFC822.match(s):
        return "RFC822"
    if SLASHED.match(s):
        return "DD/MM/YYYY"
    return "free"


class I3FormatConsistency(BaseCheck):
    check_id = "I3"
    dimension = "format_consistency"

    def run(self, dataset: Any) -> CheckResult:
        formats_seen: set[str] = set()
        examples: dict[str, str] = {}
        affected: set[str] = set()
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                refs = (record.get("payload") or {}).get("news_references") or []
                for ref in refs:
                    pa = ref.get("published_at")
                    if not pa:
                        continue
                    cls = _classify(str(pa))
                    if cls not in formats_seen:
                        examples[cls] = str(pa)
                    formats_seen.add(cls)
                    if cls != "ISO-8601":
                        affected.add(ticker)
        count = len(formats_seen)
        sev = severity_for("I3", value=count, kind="format_count")
        finding = Finding(
            module="news_references", jsonpath="$.payload.news_references[*].published_at",
            detail={"formats_seen": sorted(formats_seen),
                    "examples": examples,
                    "affected_tickers_count": len(affected)},
        )
        rec = (
            "Normalize published_at to ISO-8601 in collector (src/collector/news.py, sec.py)."
            if sev != "pass" else None
        )
        return CheckResult(
            check_id="I3",
            severity=sev,
            pass_rate=1.0 if count <= 1 else (1.0 / count),
            findings=(finding,) if formats_seen else (),
            metrics={"format_count": float(count)},
            recommendation=rec,
        )
