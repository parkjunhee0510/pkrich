from __future__ import annotations

from typing import Any


def build_ticker_timelines(days: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    timelines: dict[str, list[dict[str, Any]]] = {}
    ordered_days = sorted(
        [day for day in days if isinstance(day, dict) and isinstance(day.get("date"), str)],
        key=lambda day: day["date"],
        reverse=True,
    )

    for day in ordered_days:
        for ticker_entry in day.get("tickers", []):
            if not isinstance(ticker_entry, dict):
                continue
            ticker = str(ticker_entry.get("ticker", "")).strip()
            if not ticker:
                continue
            first_news = _first_news_reference(ticker_entry)
            timelines.setdefault(ticker, []).append(
                {
                    "date": day["date"],
                    "price": ticker_entry.get("data_snapshot", {}).get("Price", "N/A"),
                    "daily_change": ticker_entry.get("data_snapshot", {}).get("Daily Change", "N/A"),
                    "signal_or_takeaway": ticker_entry.get("signal_or_takeaway", ""),
                    "top_news_summary": _top_news_summary(ticker_entry),
                    "top_news_link": first_news.get("link", "") if first_news else "",
                    "news_tone": ticker_entry.get("news_tone", {"label": "neutral", "score": 0.0}),
                    "upcoming_events": ticker_entry.get("upcoming_events", []),
                }
            )
    return timelines


def summarize_recent_timeline(entries: list[dict[str, Any]], limit: int = 3) -> list[str]:
    summaries: list[str] = []
    for entry in entries[:limit]:
        date_text = str(entry.get("date", ""))
        signal = str(entry.get("signal_or_takeaway", "")).strip()
        news_summary = str(entry.get("top_news_summary", "")).strip()
        parts = [part for part in [signal, news_summary] if part]
        if not parts:
            continue
        summaries.append(f"{date_text}: {' | '.join(parts)}")
    return summaries


def _top_news_summary(entry: dict[str, Any]) -> str:
    key_news = entry.get("key_news", [])
    if isinstance(key_news, list):
        for item in key_news:
            if isinstance(item, str) and item.strip():
                return item.strip()
    refs = entry.get("news_references", [])
    if isinstance(refs, list):
        for item in refs:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                if title:
                    return title
    return ""


def _first_news_reference(entry: dict[str, Any]) -> dict[str, Any] | None:
    refs = entry.get("news_references", [])
    if not isinstance(refs, list):
        return None
    for item in refs:
        if isinstance(item, dict) and item.get("title"):
            return item
    return None
