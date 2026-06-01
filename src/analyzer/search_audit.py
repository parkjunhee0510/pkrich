"""Deterministic search evidence audit for analysis claims."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Mapping

from src.output.schema import SCHEMA_VERSION
from src.types import TickerAnalysis

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CLAIM_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\s+\|\s+")
_SEC_FORM_RE = re.compile(r"\b(?:form\s*)?(?:10|8|6|20|40)\s*[- ]\s*(?:q|k|f)\b", re.IGNORECASE)
_PLACEHOLDERS = {"", "-", "n/a", "na", "\u2014"}
_INTERNAL_MARKET_TERMS = (
    "주가",
    "현재가",
    "달러",
    "usd",
    "sma",
    "sma50",
    "sma200",
    "rsi",
    "52주",
    "52w",
    "30d",
    "30일",
    "7d",
    "7일",
    "atr",
    "rvol",
    "maxpain",
    "netΔ",
    "netdelta",
    "net delta",
    "옵션",
    "call",
    "put",
    "고점",
    "저점",
    "진입 트리거",
    "진입",
    "목표",
    "손절",
    "돌파",
    "이탈",
    "저항",
    "지지",
    "rs vs sector",
    "sector etf",
    "per",
    "p/e",
    "roe",
    "fcf",
    "yield",
    "forward eps",
    "ttm eps",
    "eps growth",
    "pcr",
    "oi p/c",
    "short float",
    "market cap",
    "analyst target",
    "analyst buy",
    "price target",
    "next earnings",
    "시가총액",
    "성장률",
    "entry",
    "target",
    "stop",
    "support",
    "resistance",
)
_EXTERNAL_EVIDENCE_TERMS = (
    "revenue",
    "sales",
    "guidance",
    "backlog",
    "margin",
    "dividend",
    "filing",
    "filed",
    "files",
    "reported",
    "reports",
    "report",
    "results",
    "announced",
    "beat",
    "beats",
    "miss",
    "misses",
    "upgrade",
    "downgrade",
    "sec",
    "contract",
    "demand",
    "supply",
    "lawsuit",
    "regulatory",
    "recall",
    "매출",
    "실적",
    "가이던스",
    "백로그",
    "수주",
    "마진",
    "배당",
    "공시",
    "계약",
    "수요",
    "공급",
    "소송",
    "규제",
    "리콜",
    "제출",
    "발표",
    "호조",
)


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
        for claim in _claim_fragments(text):
            normalized = claim.lower()
            if normalized in _PLACEHOLDERS or normalized in seen:
                continue
            if not _is_web_auditable_claim(claim):
                continue
            seen.add(normalized)
            claims.append({"field": field, "claim": claim})
            if len(claims) >= max_claims:
                return claims
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
    normalized = _SEC_FORM_RE.sub(" ", str(text or ""))
    return set(_NUMBER_RE.findall(normalized))


def _claim_fragments(text: Any) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    fragments: list[str] = []
    for line in value.splitlines():
        stripped = line.strip(" \t-*•")
        if not stripped:
            continue
        fragments.extend(part.strip() for part in _CLAIM_SPLIT_RE.split(stripped) if part.strip())
    return fragments


def _is_web_auditable_claim(claim: str) -> bool:
    normalized = str(claim or "").casefold()
    tokens = _tokenize(claim)
    has_internal_market_term = _has_term(normalized, tokens, _INTERNAL_MARKET_TERMS)
    has_external_evidence_term = _has_term(normalized, tokens, _EXTERNAL_EVIDENCE_TERMS)
    if has_internal_market_term and not has_external_evidence_term:
        return False
    return has_external_evidence_term


def _has_term(normalized_text: str, tokens: set[str], terms: tuple[str, ...]) -> bool:
    for term in terms:
        normalized_term = term.casefold()
        if term.isascii():
            term_tokens = _tokenize(normalized_term)
            if term_tokens and term_tokens <= tokens:
                return True
            continue
        if normalized_term in normalized_text:
            return True
    return False


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
