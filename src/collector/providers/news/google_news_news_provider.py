"""Google News NewsProvider — wraps the 6 Google News RSS site-filter feeds
that the legacy `collect_news_for_watchlist()` iterates over.

The six site filters (Google News, Yahoo Finance, Reuters, Associated Press,
CNBC, MarketWatch) are deliberately kept under ONE provider because:
  * They all hit `news.google.com/rss/search?q=...&site=...` — same host,
    same feedparser, same rate shape.
  * Each item's `NewsItem.source` carries the real outlet name (Reuters, AP,
    etc.), so the orchestrator's `source_priority` ranking still works
    downstream — the provider identity is just "how we fetched it", not
    "what it is".

`source_priority` is 1 here (below SEC=4 and IR=2). The real trust tier
lives on the individual NewsItem's source field, which the orchestrator
ranks via its own priority table in `news_rss.load_source_priorities`.

Per-item prerequisites
----------------------
`is_available(ctx)` returns False when the external-fetch env flag is off
or when `news.google.com:443` is unreachable — we can't fetch from an
unreachable host, so skip rather than fail.
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

from src.collector.base import RateLimit
from src.collector.news_base import NewsContext, NewsProvider, NewsResult
from src.types import NewsItem, WatchlistItem
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

# Mirrors the legacy _GOOGLE_NEWS_PROVIDERS list in news_rss.py.
# Order matters — the first feed is the generic Google News aggregator;
# later entries narrow to specific outlets via `site:` filter.
_GOOGLE_NEWS_FEEDS: tuple[dict[str, str], ...] = (
    {"name": "Google News", "site_filter": ""},
    {"name": "Yahoo Finance", "site_filter": "finance.yahoo.com"},
    {"name": "Reuters", "site_filter": "reuters.com"},
    {"name": "Associated Press", "site_filter": "apnews.com"},
    {"name": "CNBC", "site_filter": "cnbc.com"},
    {"name": "MarketWatch", "site_filter": "marketwatch.com"},
)

_FOCUS_TERMS = ("earnings", "guidance", "analyst", "upgrade", "downgrade", "outlook", "forecast", "results")
_FEED_HOST = "news.google.com"
_FEED_PORT = 443
_MAX_ITEMS_PER_FEED = 5


class GoogleNewsNewsProvider(NewsProvider):
    """Aggregated Google News RSS feeds surfaced as NewsItems."""

    name = "google_news"
    # Google News is an aggregator — many of its items will also surface
    # from primary sources (SEC/IR). Ranking inside the orchestrator still
    # favors primary, but keep this above fallback/duckduckgo.
    source_priority = 1
    # 6 feeds per ticker × N tickers. Google News tolerates bursts but
    # we stay conservative to avoid tripping any soft rate limits.
    rate_limit = RateLimit(calls_per_minute=60, burst=10)

    def is_available(self, ctx: NewsContext) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        # Honor a shared probe result if the orchestrator passed one —
        # avoids 1 TCP probe per ticker in a large watchlist.
        cached_probe = ctx.extra.get("google_news_available")
        if isinstance(cached_probe, bool):
            return cached_probe
        try:
            return can_open_tcp_connection(_FEED_HOST, _FEED_PORT)
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ctx: NewsContext) -> NewsResult:
        # Lazy import so pyproject/minimum-env installs that don't carry
        # feedparser still import this module without ImportError.
        try:
            import feedparser  # type: ignore
        except Exception as err:  # noqa: BLE001
            logger.warning("feedparser unavailable for google_news: %s", err)
            return NewsResult.failure(self.name, reason=f"feedparser_missing:{err}")

        items: list[NewsItem] = []
        for feed_meta in _GOOGLE_NEWS_FEEDS:
            items.extend(self._collect_single_feed(ctx.watchlist_item, feed_meta, feedparser))
        return NewsResult.success(self.name, items=items)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _collect_single_feed(
        self,
        item: WatchlistItem,
        feed_meta: dict[str, str],
        feedparser_mod: object,
    ) -> list[NewsItem]:
        query = _build_query(item, feed_meta["site_filter"])
        url = f"https://{_FEED_HOST}/rss/search?q={quote_plus(query)}"
        try:
            feed = feedparser_mod.parse(url)  # type: ignore[attr-defined]
        except Exception as err:  # noqa: BLE001 — per-feed failures are per-feed only
            record_pipeline_event(
                "collector", "warning", "news_provider_failed",
                ticker=item.ticker,
                source=feed_meta["name"],
                error_type=type(err).__name__,
                error_message=str(err),
            )
            return []

        entries: list[NewsItem] = []
        for raw in (feed.entries or [])[:_MAX_ITEMS_PER_FEED]:
            title = str(getattr(raw, "title", "") or "").strip()
            if not title:
                continue
            # Per-entry source override — many Google News items carry their
            # true outlet (e.g. "Bloomberg") even under the "Google News" feed.
            source_title = feed_meta["name"]
            raw_source = getattr(raw, "source", None)
            if raw_source is not None:
                try:
                    inferred = str(raw_source.get("title", "") or "").strip()
                except AttributeError:
                    inferred = ""
                if inferred:
                    source_title = inferred
            entries.append(
                NewsItem(
                    title=title,
                    source=source_title,
                    published_at=str(getattr(raw, "published", "") or ""),
                    link=str(getattr(raw, "link", "") or ""),
                )
            )
        return entries


def _build_query(item: WatchlistItem, site_filter: str) -> str:
    """Mirror the legacy _build_google_news_query logic."""
    company_name = (
        item.name.replace("Corporation", "").replace("Corp.", "").replace("Inc.", "")
    )
    company_name = " ".join(company_name.split())
    focus = " ".join(_FOCUS_TERMS[:4])
    parts = [item.ticker, company_name, "stock", *item.keywords[:2], focus]
    if site_filter:
        parts.append(f"site:{site_filter}")
    return " ".join(part for part in parts if part).strip()


__all__ = ["GoogleNewsNewsProvider"]
