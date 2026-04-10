from __future__ import annotations

try:
    import certifi  # type: ignore
except Exception:  # pragma: no cover - fallback path for minimal envs
    certifi = None  # type: ignore

from urllib.parse import quote_plus

from src.types import NewsItem, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event


def search_news(item: WatchlistItem, max_results: int = 3) -> list[NewsItem]:
    """Optional DuckDuckGo enrichment kept separate from RSS collection."""
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return []

    if not can_open_tcp_connection("duckduckgo.com", 443):
        return []

    query = build_news_query(item)

    try:
        from ddgs import DDGS  # type: ignore

        entries: list[NewsItem] = []
        ddgs = DDGS(verify=_ddgs_verify_setting())
        results = ddgs.text(
            query,
            region="wt-wt",
            safesearch="moderate",
            max_results=max_results,
        )
        for result in results or []:
            title = str(result.get("title", "")).strip()
            if not title:
                continue
            entries.append(
                NewsItem(
                    title=title,
                    source=str(result.get("source", "DuckDuckGo")).strip() or "DuckDuckGo",
                    published_at=str(result.get("date", "")).strip(),
                    link=_normalize_link(str(result.get("href", "")).strip()),
                )
            )
        return entries
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "news_provider_failed",
            ticker=item.ticker,
            source="DuckDuckGo",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []


def build_news_query(item: WatchlistItem) -> str:
    company_name = _normalize_company_name(item.name)
    keyword_text = " ".join(_normalize_keywords(item.keywords[:2]))
    focus_terms = "earnings guidance analyst upgrade downgrade outlook"
    query_parts = [
        item.ticker,
        company_name,
        "stock",
        keyword_text,
        focus_terms,
    ]
    return " ".join(part for part in query_parts if part).strip()


def _normalize_link(link: str) -> str:
    if not link:
        return ""
    if link.startswith("http://") or link.startswith("https://"):
        return link
    return f"https://duckduckgo.com/?q={quote_plus(link)}"


def _normalize_company_name(name: str) -> str:
    cleaned = name.replace("Corporation", "").replace("Corp.", "").replace("Inc.", "").strip()
    return " ".join(cleaned.split())


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    for keyword in keywords:
        cleaned = " ".join(keyword.strip().split())
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _ddgs_verify_setting() -> str | bool:
    try:
        return certifi.where() if certifi is not None else True
    except Exception:
        return True
