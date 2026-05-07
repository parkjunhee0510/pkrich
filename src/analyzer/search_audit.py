"""Deterministic search evidence audit for analysis claims."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Mapping

from src.output.schema import SCHEMA_VERSION
from src.types import TickerAnalysis

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_PLACEHOLDERS = {"", "-", "n/a", "na", "\u2014"}


def build_search_audit_payload(
    *,
    run_date: date,
    analyses: list[TickerAnalysis],
    search_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_items = [
        item
        for item in search_evidence.get("items", [])
        if isinstance(item, dict)
    ]
    ticker_payloads = [
        _audit_ticker(analysis, _ticker_evidence(analysis.ticker, evidence_items))
        for analysis in analyses
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "date": run_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "search_evidence",
        "tickers": ticker_payloads,
        "run_summary": _summarize_run(ticker_payloads),
    }


def extract_analysis_claims(analysis: TickerAnalysis, max_claims: int = 8) -> list[dict[str, str]]:
    candidates: list[tuple[str, str]] = [
        ("summary", analysis.summary),
        ("signal_or_takeaway", analysis.signal_or_takeaway),
    ]
    candidates.extend(("financial_highlights", item) for item in analysis.financial_highlights)
    candidates.extend(("risks_or_watchpoints", item) for item in analysis.risks_or_watchpoints)
    candidates.extend(("key_news", item) for item in analysis.key_news)

    claims: list[dict[str, str]] = []
    seen: set[str] = set()
    for field, text in candidates:
        claim = str(text or "").strip()
        normalized = claim.lower()
        if normalized in _PLACEHOLDERS or normalized in seen:
            continue
        seen.add(normalized)
        claims.append({"field": field, "claim": claim})
        if len(claims) >= max_claims:
            break
    return claims


def _audit_ticker(analysis: TickerAnalysis, evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    claims = extract_analysis_claims(analysis)
    issues = [
        _evaluate_claim(claim["claim"], claim["field"], evidence_items)
        for claim in claims
    ]
    counts = _status_counts(issues)
    verdict = _verdict(len(claims), counts)
    return {
        "ticker": str(analysis.ticker or "").strip().upper(),
        "verdict": verdict,
        "checked_claims": len(claims),
        "supported_claims": counts["supported"],
        "conflicting_claims": counts["conflicting"],
        "missing_evidence_claims": counts["missing_evidence"],
        "insufficient_evidence_claims": counts["insufficient_evidence"],
        "issues": issues,
    }


def _evaluate_claim(claim: str, field: str, evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not evidence_items:
        return _issue(claim, field, "insufficient_evidence")

    best_item: dict[str, Any] | None = None
    best_score = 0.0
    for item in evidence_items:
        score = _overlap_score(claim, _evidence_text(item))
        if score > best_score:
            best_score = score
            best_item = item

    claim_numbers = _numbers(claim)
    evidence_numbers = _numbers(_evidence_text(best_item or {}))
    numbers_supported = all(number in evidence_numbers for number in claim_numbers)
    has_numeric_conflict = bool(claim_numbers and evidence_numbers and not numbers_supported)

    if best_item and best_score >= 0.45 and numbers_supported:
        return _issue(claim, field, "supported", best_item, best_score)
    if best_item and best_score >= 0.35 and has_numeric_conflict:
        return _issue(claim, field, "conflicting", best_item, best_score)
    return _issue(claim, field, "missing_evidence")


def _issue(
    claim: str,
    field: str,
    status: str,
    evidence_item: Mapping[str, Any] | None = None,
    score: float = 0.0,
) -> dict[str, Any]:
    evidence_item = evidence_item or {}
    return {
        "claim": claim,
        "field": field,
        "status": status,
        "source_url": str(evidence_item.get("url") or ""),
        "source_domain": str(evidence_item.get("source_domain") or ""),
        "source_title": str(evidence_item.get("title") or ""),
        "match_score": round(score, 4),
    }


def _ticker_evidence(ticker: str, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = str(ticker or "").strip().upper()
    return [
        item
        for item in evidence_items
        if str(item.get("ticker") or "").strip().upper() == normalized
    ]


def _evidence_text(item: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "").strip()
        for key in ("title", "snippet", "evidence_type")
    )


def _overlap_score(claim: str, evidence_text: str) -> float:
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 0.0
    evidence_tokens = _tokenize(evidence_text)
    return len(claim_tokens & evidence_tokens) / len(claim_tokens)


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(str(text or ""))
        if len(token) > 1 or token.isdigit()
    }


def _numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(str(text or "")))


def _status_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "supported": sum(1 for issue in issues if issue.get("status") == "supported"),
        "conflicting": sum(1 for issue in issues if issue.get("status") == "conflicting"),
        "missing_evidence": sum(1 for issue in issues if issue.get("status") == "missing_evidence"),
        "insufficient_evidence": sum(1 for issue in issues if issue.get("status") == "insufficient_evidence"),
    }


def _verdict(checked_claims: int, counts: Mapping[str, int]) -> str:
    if checked_claims == 0:
        return "info"
    if counts.get("supported", 0) == checked_claims:
        return "pass"
    return "warn"


def _summarize_run(ticker_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ticker_count": len(ticker_payloads),
        "checked_claims": sum(int(ticker.get("checked_claims", 0)) for ticker in ticker_payloads),
        "supported_claims": sum(int(ticker.get("supported_claims", 0)) for ticker in ticker_payloads),
        "conflicting_claims": sum(int(ticker.get("conflicting_claims", 0)) for ticker in ticker_payloads),
        "missing_evidence_claims": sum(
            int(ticker.get("missing_evidence_claims", 0)) for ticker in ticker_payloads
        ),
        "insufficient_evidence_claims": sum(
            int(ticker.get("insufficient_evidence_claims", 0)) for ticker in ticker_payloads
        ),
        "issue_count": sum(len(ticker.get("issues", [])) for ticker in ticker_payloads),
    }
