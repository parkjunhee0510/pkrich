from __future__ import annotations

from datetime import date

from src.collector.news_search import search_news
from src.types import NewsItem, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection


def collect_news_for_watchlist(
    watchlist: list[WatchlistItem],
    run_date: date,
) -> dict[str, list[NewsItem]]:
    news_map: dict[str, list[NewsItem]] = {}
    for item in watchlist:
        rss_news = _collect_rss_news(item, run_date)
        search_results = search_news(item)
        news_map[item.ticker] = _merge_news_items(rss_news, search_results, max_items=5)
    return news_map


def _collect_rss_news(item: WatchlistItem, run_date: date) -> list[NewsItem]:
    if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=False):
        return _fallback_news(item, run_date, "External fetch disabled; skipped RSS request.")

    if not can_open_tcp_connection("news.google.com", 443):
        return _fallback_news(item, run_date, "Network unavailable; skipped RSS request.")

    try:
        import feedparser  # type: ignore

        query = item.ticker
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={query}+stock")
        entries = []
        for entry in feed.entries[:5]:
            entries.append(
                NewsItem(
                    title=str(getattr(entry, "title", "")).strip(),
                    source=str(getattr(entry, "source", {}).get("title", "RSS")) if hasattr(entry, "source") else "RSS",
                    published_at=str(getattr(entry, "published", "")),
                    link=str(getattr(entry, "link", "")),
                )
            )
        if entries:
            return entries
    except Exception:
        pass

    return _fallback_news(item, run_date, f"No recent news fetched for {item.ticker} as of {run_date.isoformat()}")


def _fallback_news(item: WatchlistItem, run_date: date, title: str) -> list[NewsItem]:
    return [
        NewsItem(
            title=title,
            source="fallback",
            published_at=run_date.isoformat(),
            link="",
        )
    ]


def _merge_news_items(
    primary: list[NewsItem],
    supplemental: list[NewsItem],
    max_items: int,
) -> list[NewsItem]:
    merged: list[NewsItem] = []
    seen_titles: set[str] = set()

    for item in primary + supplemental:
        normalized_title = " ".join(item.title.lower().split())
        if not normalized_title or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        merged.append(item)
        if len(merged) >= max_items:
            break

    return merged
