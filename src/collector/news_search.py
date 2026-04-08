from __future__ import annotations

from urllib.parse import quote_plus

from src.types import NewsItem, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection


def search_news(item: WatchlistItem, max_results: int = 3) -> list[NewsItem]:
    """Optional DuckDuckGo enrichment kept separate from RSS collection."""
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=False):
        return []

    if not can_open_tcp_connection("duckduckgo.com", 443):
        return []

    query_parts = [item.ticker, item.name, "stock news"]
    query_parts.extend(item.keywords[:2])
    query = " ".join(part for part in query_parts if part)

    try:
        from duckduckgo_search import DDGS  # type: ignore

        entries: list[NewsItem] = []
        with DDGS() as ddgs:
            results = ddgs.text(
                keywords=query,
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
    except Exception:
        return []


def _normalize_link(link: str) -> str:
    if not link:
        return ""
    if link.startswith("http://") or link.startswith("https://"):
        return link
    return f"https://duckduckgo.com/?q={quote_plus(link)}"
