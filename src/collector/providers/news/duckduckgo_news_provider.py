"""DuckDuckGo NewsProvider — wraps src.collector.news_search.search_news().

DuckDuckGo is a supplemental search enrichment in the legacy pipeline
(source_priority 0). It fills gaps when a ticker has nothing fresh from
Google News or SEC EDGAR, but its items are the lowest-trust — they're
often blog aggregators or reposts. Keep `source_priority` at 0 so the
orchestrator's dedup step drops DuckDuckGo copies of any headline that
also appeared from a real source.

Per-item prerequisites
----------------------
`is_available(ctx)` returns False when external fetch is disabled or
`duckduckgo.com:443` is unreachable. Honors `ctx.extra["duckduckgo_available"]`
when the orchestrator has already probed.
"""
from __future__ import annotations

import logging

from src.collector import news_search as news_search_module
from src.collector.base import RateLimit
from src.collector.news_base import NewsContext, NewsProvider, NewsResult
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection

logger = logging.getLogger(__name__)

_HOST = "duckduckgo.com"
_PORT = 443
_DEFAULT_MAX_RESULTS = 3


class DuckDuckGoNewsProvider(NewsProvider):
    """DuckDuckGo supplemental search results."""

    name = "duckduckgo"
    source_priority = 0  # below IR / Google News — supplemental only
    # DuckDuckGo rate-limits aggressively. Keep well under any published
    # ceiling to avoid 429s during a large watchlist run.
    rate_limit = RateLimit(calls_per_minute=30, burst=5)

    def is_available(self, ctx: NewsContext) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        cached_probe = ctx.extra.get("duckduckgo_available")
        if isinstance(cached_probe, bool):
            return cached_probe
        try:
            return can_open_tcp_connection(_HOST, _PORT)
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ctx: NewsContext) -> NewsResult:
        try:
            items = news_search_module.search_news(
                ctx.watchlist_item,
                max_results=_DEFAULT_MAX_RESULTS,
            )
        except Exception as err:  # noqa: BLE001 — never raise
            logger.exception("duckduckgo news provider failed for %s", ctx.watchlist_item.ticker)
            return NewsResult.failure(self.name, reason=f"exception:{err}")

        return NewsResult.success(self.name, items=items)


__all__ = ["DuckDuckGoNewsProvider"]
