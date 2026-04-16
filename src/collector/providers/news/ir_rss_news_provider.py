"""IR RSS NewsProvider — wraps collect_ir_rss_news() in the new contract.

Company IR RSS feeds (Apple Newsroom, Microsoft Source, NVIDIA Newsroom,
etc.) are *primary* corporate communication — anything important the
company wants the market to know shows up here first. source_priority 2
matches the legacy table: above random blogs and below Reuters/AP/SEC.

Per-item prerequisites
----------------------
`is_available(ctx)` returns False unless `watchlist_item.ir_rss_feeds`
has at least one URL. Without a feed URL there's nothing to fetch.
"""
from __future__ import annotations

import logging

from src.collector import ir_rss as ir_rss_module
from src.collector.base import RateLimit
from src.collector.news_base import NewsContext, NewsProvider, NewsResult
from src.utils.env import is_env_flag_enabled

logger = logging.getLogger(__name__)


class IRRSSNewsProvider(NewsProvider):
    """Company IR RSS feeds surfaced as NewsItems."""

    name = "ir_rss"
    source_priority = 2
    # Each feed request is to a company CDN; no shared quota. Conservative
    # cpm keeps us friendly to those CDNs even when parallelized.
    rate_limit = RateLimit(calls_per_minute=60, burst=15)

    def is_available(self, ctx: NewsContext) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        # `ir_rss_feeds` is empty for most tickers — skip instead of failing.
        return bool(ctx.watchlist_item.ir_rss_feeds)

    def collect(self, ctx: NewsContext) -> NewsResult:
        try:
            items = ir_rss_module.collect_ir_rss_news(ctx.watchlist_item)
        except Exception as err:  # noqa: BLE001
            logger.exception("ir_rss news provider failed for %s", ctx.watchlist_item.ticker)
            return NewsResult.failure(self.name, reason=f"exception:{err}")

        return NewsResult.success(self.name, items=items)


__all__ = ["IRRSSNewsProvider"]
