from __future__ import annotations

import gzip
import json
import os
import re
from datetime import date
from typing import Any
from urllib import request

from src.types import NewsItem, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

_SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
def sec_user_agent() -> str:
    """User-Agent for SEC EDGAR requests.

    SEC's fair-access policy requires a real contact (email). Set
    SEC_CONTACT_EMAIL to a valid address; otherwise we fall back to a
    placeholder that SEC may rate-limit or block.
    """
    contact = os.getenv("SEC_CONTACT_EMAIL", "").strip() or "local-automation"
    return f"pkrich-stock-research/1.0 (contact: {contact})"
_DEFAULT_MAX_FILINGS = 3
_ITEM_PATTERN = re.compile(r"item\s+(\d+\.\d+)", re.IGNORECASE)
_RELEVANT_FORMS = {
    "8-K": {"category": "기타 공시", "description": "중요 사항 공시용 보고서", "catalyst_type": "medium", "importance_score": 120},
    "8-K/A": {"category": "기타 공시", "description": "중요 사항 정정 공시 보고서", "catalyst_type": "medium", "importance_score": 100},
    "10-Q": {"category": "실적", "description": "분기 실적 관련 보고서", "catalyst_type": "hard", "importance_score": 200},
    "10-K": {"category": "실적", "description": "연간 사업 및 재무 보고서", "catalyst_type": "hard", "importance_score": 190},
    "6-K": {"category": "기타 공시", "description": "해외 발행사 공시 보고서", "catalyst_type": "medium", "importance_score": 110},
    "20-F": {"category": "실적", "description": "해외 발행사 연간 보고서", "catalyst_type": "hard", "importance_score": 190},
    "DEF 14A": {"category": "주주총회", "description": "주주총회 관련 위임장 설명서", "catalyst_type": "medium", "importance_score": 100},
}
_8K_ITEM_MAP: dict[str, tuple[str, str, int]] = {
    "2.02": ("실적 발표", "hard", 200),
    "5.02": ("임원 교체", "hard", 180),
    "1.01": ("주요 계약", "hard", 160),
    "8.01": ("기타 중요 공시", "medium", 120),
    "7.01": ("Reg FD 공시", "medium", 100),
    "1.05": ("중요 사이버보안", "hard", 150),
    "2.01": ("자산 취득/처분", "medium", 130),
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
            "User-Agent": sec_user_agent(),
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
    _ = run_date
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

        metadata = _build_filing_metadata(
            normalized_form,
            primary_document=str(primary_document or ""),
            primary_description=str(primary_description or ""),
        )
        title = _build_filing_title(company_name, normalized_form, metadata)
        news_items.append(
            NewsItem(
                title=title,
                source="SEC EDGAR",
                published_at=filed_on,
                link=_build_filing_link(item.cik, str(accession_number or ""), str(primary_document or "")),
                form_type=normalized_form,
                item_number=metadata["item_number"],
                catalyst_type=metadata["catalyst_type"],
                importance_score=metadata["importance_score"],
            )
        )

    return sorted(
        news_items,
        key=lambda filing: (filing.published_at, filing.importance_score, filing.title),
        reverse=True,
    )[:max_items]


def _build_filing_title(company_name: str, form: str, metadata: dict[str, Any]) -> str:
    tag = metadata["category"]
    description = metadata["description"]
    item_number = metadata["item_number"]
    if item_number:
        return f"[{tag}] {company_name}, {form} Item {item_number} {description}를 SEC에 제출"
    return f"[{tag}] {company_name}, {form} {description}를 SEC에 제출"


def _build_filing_metadata(
    form: str,
    *,
    primary_document: str,
    primary_description: str,
) -> dict[str, Any]:
    base = _RELEVANT_FORMS.get(form, _RELEVANT_FORMS["8-K"])
    normalized_text = f"{primary_document} {primary_description}".strip().lower()
    item_number = _parse_8k_item_number(primary_document) or _parse_8k_item_number(primary_description)

    category = _classify_filing_category(
        form,
        default_category=str(base.get("category", "기타 공시")),
        primary_document=primary_document,
        primary_description=primary_description,
        item_number=item_number,
    )

    catalyst_type = str(base.get("catalyst_type", "medium"))
    importance_score = int(base.get("importance_score", 100))
    description = str(base.get("description", "SEC 공시"))

    if form.startswith("8-K") and item_number:
        item_meta = _8K_ITEM_MAP.get(item_number)
        if item_meta is not None:
            description, catalyst_type, importance_score = item_meta
            if item_number == "2.02":
                category = "실적"
    elif "dividend" in normalized_text or "distribution" in normalized_text:
        catalyst_type = "medium"
        importance_score = max(importance_score, 110)
        description = "배당 관련 공시"
    elif "proxy" in normalized_text or "annual meeting" in normalized_text or "shareholder" in normalized_text:
        catalyst_type = "medium"
        importance_score = max(importance_score, 100)

    return {
        "category": category,
        "description": description,
        "item_number": item_number,
        "catalyst_type": catalyst_type,
        "importance_score": importance_score,
    }


def _parse_8k_item_number(text: str) -> str:
    match = _ITEM_PATTERN.search(text or "")
    if not match:
        return ""
    return match.group(1)


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
    item_number: str,
) -> str:
    normalized_text = f"{primary_document} {primary_description}".strip().lower()
    if form.startswith("8-K") and item_number == "2.02":
        return "실적"
    if "dividend" in normalized_text or "distribution" in normalized_text:
        return "배당"
    if "proxy" in normalized_text or "annual meeting" in normalized_text or "shareholder" in normalized_text:
        return "주주총회"
    if form in {"10-Q", "10-K", "20-F"}:
        return "실적"
    if form == "DEF 14A":
        return "주주총회"
    return default_category
