from __future__ import annotations

import re
from typing import Any

from src.eval.checks.base import BaseCheck, CheckResult, Finding
from src.eval.config import severity_for


def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[\w가-힣]+", (s or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class O3CitationIntegrity(BaseCheck):
    check_id = "O3"
    dimension = "citation_integrity"

    def __init__(self, check_links: bool = False, link_sample_cap: int = 100) -> None:
        self.check_links = check_links
        self.link_sample_cap = link_sample_cap

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        matched = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                key_news = payload.get("key_news") or []
                refs = payload.get("news_references") or []
                ref_titles = [r.get("title") or "" for r in refs]
                for kn in key_news:
                    total += 1
                    best = max((_jaccard(kn, t) for t in ref_titles), default=0.0)
                    if best >= 0.85:
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.key_news",
                            detail={"orphan": kn, "best_jaccard": best},
                        ))
        rate = (matched / total) if total else 1.0
        sev = severity_for("O3", value=rate, kind="citation_match_rate")
        return CheckResult(
            check_id="O3",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"citation_match_rate": rate,
                     "total_key_news": float(total),
                     "link_check_enabled": float(self.check_links)},
            recommendation=(
                "Constrain prompt: 'key_news must be drawn from news_references list verbatim'."
                if sev != "pass" else None
            ),
        )
