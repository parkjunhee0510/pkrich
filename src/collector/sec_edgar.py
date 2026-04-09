from __future__ import annotations

import gzip
import json
from datetime import date
from typing import Any
from urllib import request

from src.types import NewsItem, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_SEC_USER_AGENT = "pkrich-stock-research/1.0 (contact: local-automation)"
_DEFAULT_MAX_FILINGS = 3
_RELEVANT_FORMS = {
    "8-K": {"category": "기타 공시", "description": "중요 사항 공시용 보고서"},
    "8-K/A": {"category": "기타 공시", "description": "중요 사항 정정 공시 보고서"},
    "10-Q": {"category": "실적", "description": "분기 실적 관련 보고서"},
    "10-K": {"category": "실적", "description": "연간 사업 및 재무 보고서"},
    "6-K": {"category": "기타 공시", "description": "해외발행인 수시 보고서"},
    "20-F": {"category": "실적", "description": "해외발행인 연간 보고서"},
    "DEF 14A": {"category": "주주총회", "description": "주주총회 관련 위임장 설명서"},
}


def collect_sec_edgar_news(
    item: WatchlistItem,
    run_date: date,
    *,
    network_available: bool | None = None,
    max_items: int = _DEFAULT_MAX_FILINGS,
) -> list[NewsItem]:
    if not item.cik or not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return []

    if network_available is None:
        network_available = can_open_tcp_connection("data.sec.gov", 443)
    if not network_available:
        return []

    try:
        payload = _download_submissions_payload(item.cik)
        filings = _extract_recent_filings(payload, item, run_date, max_items=max_items)
        if filings:
            record_pipeline_event(
                "collector",
                "info",
                "news_provider_completed",
                ticker=item.ticker,
                source="SEC EDGAR",
                result_count=len(filings),
            )
        return filings
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "news_provider_failed",
            ticker=item.ticker,
            source="SEC EDGAR",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def _download_submissions_payload(cik: str) -> dict[str, Any]:
    request_url = _SEC_SUBMISSIONS_URL.format(cik=cik)
    sec_request = request.Request(
        request_url,
        headers={
            "User-Agent": _SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        },
    )
    with request.urlopen(sec_request, timeout=15) as response:
        response_bytes = response.read()
        encoding = str(response.headers.get("Content-Encoding", "")).lower()
        if encoding == "gzip" or response_bytes[:2] == b"\x1f\x8b":
            response_bytes = gzip.decompress(response_bytes)
        payload = json.loads(response_bytes.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _extract_recent_filings(
    payload: dict[str, Any],
    item: WatchlistItem,
    run_date: date,
    *,
    max_items: int,
) -> list[NewsItem]:
    filings = payload.get("filings", {})
    recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
    forms = _coerce_list(recent.get("form"))
    filing_dates = _coerce_list(recent.get("filingDate"))
    accession_numbers = _coerce_list(recent.get("accessionNumber"))
    primary_documents = _coerce_list(recent.get("primaryDocument"))
    primary_descriptions = _coerce_list(recent.get("primaryDocDescription"))

    company_name = str(payload.get("name", "")).strip() or item.name
    news_items: list[NewsItem] = []
    for form, filing_date, accession_number, primary_document, primary_description in zip(
        forms,
        filing_dates,
        accession_numbers,
        primary_documents,
        _pad_list(primary_descriptions, len(forms)),
    ):
        normalized_form = str(form or "").strip().upper()
        if normalized_form not in _RELEVANT_FORMS:
            continue
        filed_on = str(filing_date or "").strip()
        if not filed_on:
            continue
        title = _build_filing_title(
            company_name,
            normalized_form,
            primary_document=str(primary_document or ""),
            primary_description=str(primary_description or ""),
        )
        news_items.append(
            NewsItem(
                title=title,
                source="SEC EDGAR",
                published_at=filed_on,
                link=_build_filing_link(item.cik, str(accession_number or ""), str(primary_document or "")),
            )
        )

    return sorted(
        news_items,
        key=lambda filing: (filing.published_at, filing.title),
        reverse=True,
    )[:max_items]


def _build_filing_title(
    company_name: str,
    form: str,
    *,
    primary_document: str = "",
    primary_description: str = "",
) -> str:
    filing_meta = _RELEVANT_FORMS.get(form, {"category": "기타 공시", "description": "SEC 공시"})
    category = _classify_filing_category(
        form,
        default_category=str(filing_meta.get("category", "기타 공시")),
        primary_document=primary_document,
        primary_description=primary_description,
    )
    description = str(filing_meta.get("description", "SEC 공시"))
    return f"[{category}] {company_name}, {form} {description}를 SEC에 제출"


def _build_filing_link(cik: str, accession_number: str, primary_document: str) -> str:
    normalized_accession = accession_number.replace("-", "").strip()
    normalized_cik = str(int(cik)) if cik.strip().isdigit() else cik.strip()
    if normalized_cik and normalized_accession and primary_document:
        return f"https://www.sec.gov/Archives/edgar/data/{normalized_cik}/{normalized_accession}/{primary_document}"
    if normalized_cik:
        return f"https://data.sec.gov/submissions/CIK{cik}.json"
    return ""


def _coerce_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _pad_list(values: list[Any], target_length: int) -> list[Any]:
    if len(values) >= target_length:
        return values
    return values + [""] * (target_length - len(values))


def _classify_filing_category(
    form: str,
    *,
    default_category: str,
    primary_document: str,
    primary_description: str,
) -> str:
    normalized_text = f"{primary_document} {primary_description}".strip().lower()
    if "dividend" in normalized_text or "distribution" in normalized_text:
        return "배당"
    if "proxy" in normalized_text or "annual meeting" in normalized_text or "shareholder" in normalized_text:
        return "주주총회"
    if form in {"10-Q", "10-K", "20-F"}:
        return "실적"
    if form == "DEF 14A":
        return "주주총회"
    return default_category
