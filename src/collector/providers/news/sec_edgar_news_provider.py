"""SEC EDGAR NewsProvider — wraps collect_sec_edgar_news() in the new contract.

SEC EDGAR is the single most-trusted news source for US equities because
filings are legally required and timestamped. The provider inherits the
legacy collector's per-form classification (8-K / 10-K / 10-Q + Item
numbers for 8-K catalyst_type detection) and emits them as NewsItem
instances with `source="SEC EDGAR"` so the orchestrator can rank them
against Reuters/AP/IR feeds.

Per-item prerequisites
----------------------
`is_available(ctx)` returns False unless the watchlist item has a `cik`
field set. Without CIK, we can't query the submissions endpoint. This
mirrors the legacy behavior (`collect_sec_edgar_news` short-circuits on
empty CIK) and makes the skip visible to the orchestrator for reporting.
"""
from __future__ import annotations

import logging

from src.collector import sec_edgar as sec_edgar_module
from src.collector.base import RateLimit
from src.collector.news_base import NewsContext, NewsProvider, NewsResult
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection

logger = logging.getLogger(__name__)

_SEC_HOST = "data.sec.gov"
_SEC_PORT = 443


class SECEdgarNewsProvider(NewsProvider):
    """SEC EDGAR filings surfaced as NewsItems.

    source_priority 4 matches Reuters/AP tier — SEC filings are primary
    source material. Rate is conservative (SEC asks for ≤10 req/sec; we
    cap at 60 cpm so we never get close even under parallelization).
    """

    name = "sec_edgar"
    source_priority = 4
    rate_limit = RateLimit(calls_per_minute=60, burst=10)

    def is_available(self, ctx: NewsContext) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        if not ctx.watchlist_item.cik:
            # Not an error — many tickers don't have CIK set. Skip quietly.
            return False
        # Honor a shared TCP probe result if the orchestrator passed one.
        cached_probe = ctx.extra.get("sec_edgar_available")
        if isinstance(cached_probe, bool):
            return cached_probe
        try:
            return can_open_tcp_connection(_SEC_HOST, _SEC_PORT)
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ctx: NewsContext) -> NewsResult:
        try:
            # `network_available=True` here avoids a second TCP probe —
            # is_available already did it.
            items = sec_edgar_module.collect_sec_edgar_news(
                ctx.watchlist_item,
                ctx.run_date,
                network_available=True,
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("sec_edgar news provider failed for %s", ctx.watchlist_item.ticker)
            return NewsResult.failure(self.name, reason=f"exception:{err}")

        if not items:
            # No filings within the lookback window — that's a neutral outcome.
            return NewsResult.success(self.name, items=[])
        return NewsResult.success(self.name, items=items)


__all__ = ["SECEdgarNewsProvider"]
