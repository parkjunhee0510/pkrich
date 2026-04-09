from __future__ import annotations

import re
from typing import Any

from src.types import NewsItem

_SEC_TAG_PATTERN = re.compile(r"^\[(?P<tag>[^\]]+)\]\s*(?P<title>.+)$")
_SEC_FORM_PATTERN = re.compile(
    r"\b(10-Q|10-K|8-K|6-K|20-F|DEF 14A|S-8|13D|13G|SC 13D|SC 13G)\b",
    flags=re.IGNORECASE,
)


def is_sec_filing_reference(item: NewsItem) -> bool:
    return (item.source or "").strip().lower() == "sec edgar"


def extract_sec_filing_tag(title: str) -> str:
    match = _SEC_TAG_PATTERN.match((title or "").strip())
    if not match:
        return ""
    return match.group("tag").strip()


def strip_sec_filing_tag(title: str) -> str:
    match = _SEC_TAG_PATTERN.match((title or "").strip())
    if not match:
        return (title or "").strip()
    return match.group("title").strip()


def extract_sec_form_type(title: str) -> str:
    cleaned = strip_sec_filing_tag(title)
    match = _SEC_FORM_PATTERN.search(cleaned)
    if not match:
        return ""
    return match.group(1).upper()


def collect_sec_filings(news_references: list[NewsItem]) -> list[dict[str, str]]:
    filings: list[dict[str, str]] = []
    for item in news_references:
        if not is_sec_filing_reference(item):
            continue
        title = strip_sec_filing_tag(item.title)
        filings.append(
            {
                "tag": extract_sec_filing_tag(item.title),
                "title": title,
                "form_type": extract_sec_form_type(title),
                "published_at": item.published_at,
                "link": item.link,
                "source": item.source,
            }
        )
    return filings


def collect_sec_filing_tags(news_references: list[NewsItem]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for filing in collect_sec_filings(news_references):
        tag = filing.get("tag", "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags


def sort_sec_filings(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        filings,
        key=lambda item: (str(item.get("published_at", "")), str(item.get("title", ""))),
        reverse=True,
    )
