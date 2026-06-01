from __future__ import annotations

from urllib.parse import urlparse

from src.types import NewsItem, WatchlistItem
from src.utils.config import load_simple_mapping
from src.utils.env import is_env_flag_enabled
from src.utils.pipeline_logging import record_pipeline_event
from src.collector.feed_fetch import parse_feed

_DEFAULT_MAX_ITEMS_PER_FEED = 5
_DEFAULT_IR_SOURCE_NAME_BY_HOST = {
    'www.apple.com': 'Apple Newsroom',
    'apple.com': 'Apple Newsroom',
    'news.microsoft.com': 'Microsoft Source',
    'nvidianews.nvidia.com': 'NVIDIA Newsroom',
}


def collect_ir_rss_news(
    item: WatchlistItem,
    *,
    max_items_per_feed: int = _DEFAULT_MAX_ITEMS_PER_FEED,
) -> list[NewsItem]:
    if not item.ir_rss_feeds or not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
        return []

    try:
        import feedparser  # type: ignore
    except Exception as exc:
        record_pipeline_event(
            "collector",
            "warning",
            "news_provider_failed",
            ticker=item.ticker,
            source="IR RSS",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return []

    collected: list[NewsItem] = []
    for feed_url in item.ir_rss_feeds:
        try:
            feed = parse_feed(feed_url)
            source_name = _resolve_ir_source_name(item, feed, feed_url)
            feed_items = 0
            for entry in getattr(feed, "entries", [])[:max_items_per_feed]:
                title = str(getattr(entry, "title", "")).strip()
                if not title:
                    continue
                collected.append(
                    NewsItem(
                        title=title,
                        source=source_name,
                        published_at=str(getattr(entry, "published", "")).strip(),
                        link=str(getattr(entry, "link", "")).strip(),
                    )
                )
                feed_items += 1
            record_pipeline_event(
                "collector",
                "info",
                "news_provider_completed",
                ticker=item.ticker,
                source=source_name,
                feed_url=feed_url,
                result_count=feed_items,
            )
        except Exception as exc:
            record_pipeline_event(
                "collector",
                "warning",
                "news_provider_failed",
                ticker=item.ticker,
                source="IR RSS",
                feed_url=feed_url,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
    return collected


def _resolve_ir_source_name(item: WatchlistItem, feed: object, feed_url: str) -> str:
    feed_meta = getattr(feed, 'feed', None)
    title = str(getattr(feed_meta, 'title', '')).strip() if feed_meta is not None else ''
    if title:
        normalized = _normalize_feed_title(title)
        if normalized:
            return normalized

    hostname = (urlparse(feed_url).hostname or '').strip().lower()
    configured_source_names = _load_ir_source_names(item)
    normalized_feed_url = feed_url.strip().lower()
    if normalized_feed_url in configured_source_names:
        return configured_source_names[normalized_feed_url]
    if hostname in configured_source_names:
        return configured_source_names[hostname]
    normalized_hostname = _normalize_hostname(hostname)
    if normalized_hostname in configured_source_names:
        return configured_source_names[normalized_hostname]

    if hostname:
        domain_root = hostname.split('.')
        if len(domain_root) >= 2:
            return f"{domain_root[-2].upper()} IR"
    return 'IR RSS'


def _normalize_feed_title(title: str) -> str:
    normalized = " ".join(title.split())
    lowered = normalized.lower()
    if lowered in {'apple newsroom', 'microsoft source', 'nvidia newsroom'}:
        return normalized
    if 'apple' in lowered and 'newsroom' in lowered:
        return 'Apple Newsroom'
    if 'microsoft' in lowered and 'source' in lowered:
        return 'Microsoft Source'
    if 'nvidia' in lowered and ('newsroom' in lowered or 'news' in lowered):
        return 'NVIDIA Newsroom'
    return normalized


def _load_ir_source_names(item: WatchlistItem) -> dict[str, str]:
    configured: dict[str, str] = {}
    try:
        raw_config = load_simple_mapping("config/output.yaml")
        raw_mapping = raw_config.get("ir_source_names", {})
        if isinstance(raw_mapping, dict):
            for key, value in raw_mapping.items():
                normalized_key = str(key).strip().lower()
                normalized_value = str(value).strip()
                if normalized_key and normalized_value:
                    configured[normalized_key] = normalized_value
    except Exception:
        configured = {}

    merged = dict(_DEFAULT_IR_SOURCE_NAME_BY_HOST)
    merged.update(configured)
    merged.update(_normalize_item_ir_source_names(item.ir_source_names))
    return merged


def _normalize_hostname(hostname: str) -> str:
    normalized = hostname.strip().lower()
    if normalized.startswith('www.'):
        return normalized[4:]
    return normalized


def _normalize_item_ir_source_names(mapping: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in mapping.items():
        normalized_key = str(key).strip().lower()
        normalized_value = str(value).strip()
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized
