from __future__ import annotations

import re
import urllib.request
from typing import Any, Callable

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

    def __init__(
        self,
        check_links: bool = False,
        link_sample_cap: int = 100,
        link_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self.check_links = check_links
        self.link_sample_cap = link_sample_cap
        self.link_checker = link_checker or _head_ok

    def run(self, dataset: Any) -> CheckResult:
        total = 0
        matched = 0
        link_total = 0
        link_ok = 0
        findings: list[Finding] = []
        for ticker, days in dataset.daily.items():
            for d, record in days.items():
                payload = record.get("payload") or {}
                key_news = payload.get("key_news") or []
                refs = payload.get("news_references") or []
                ref_titles = [r.get("title") or "" for r in refs]
                source_titles = payload.get("key_news_source_titles") or []
                if self.check_links:
                    for ref in refs:
                        if link_total >= self.link_sample_cap:
                            break
                        link = str(ref.get("link") or "").strip()
                        if not link:
                            continue
                        link_total += 1
                        if self.link_checker(link):
                            link_ok += 1
                        else:
                            findings.append(Finding(
                                ticker=ticker, date=d,
                                jsonpath="$.payload.news_references[*].link",
                                detail={"link": link, "reason": "head_check_failed"},
                            ))
                for index, kn in enumerate(key_news):
                    total += 1
                    candidate = (
                        str(source_titles[index])
                        if index < len(source_titles) and str(source_titles[index]).strip()
                        else str(kn)
                    )
                    best = max((_jaccard(candidate, t) for t in ref_titles), default=0.0)
                    if best >= 0.85:
                        matched += 1
                    else:
                        findings.append(Finding(
                            ticker=ticker, date=d, jsonpath="$.payload.key_news",
                            detail={"orphan": kn, "source_title": candidate, "best_jaccard": best},
                        ))
        rate = (matched / total) if total else 1.0
        sev = severity_for("O3", value=rate, kind="citation_match_rate")
        link_rate = (link_ok / link_total) if link_total else 1.0
        if self.check_links and link_rate < 0.90:
            sev = "fail"
        return CheckResult(
            check_id="O3",
            severity=sev,
            pass_rate=rate,
            findings=tuple(findings[:50]),
            metrics={"citation_match_rate": rate,
                     "total_key_news": float(total),
                     "sample_count": float(total),
                     "link_check_enabled": float(self.check_links),
                     "link_success_rate": link_rate,
                     "link_sample_count": float(link_total)},
            recommendation=(
                "Constrain prompt: 'key_news must be drawn from news_references list verbatim'."
                if sev != "pass" else None
            ),
        )


def _head_ok(url: str) -> bool:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=5) as response:
            return 200 <= int(response.status) < 400
    except Exception:
        return False
