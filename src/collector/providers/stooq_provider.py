"""Stooq DataProvider — priority-3 price fallback when yfinance is unreachable.

Stooq exposes a simple CSV endpoint (stooq.com/q/d/l/) with end-of-day
close history for global tickers. We use it for two things only:
  * Today's close and % change when yfinance is unavailable
  * Best-effort historical prices for the 6-month window

Anything richer (fundamentals, options, news) is out of scope — Stooq's
coverage is thin and stale. Keeping this provider narrow makes it a
trustworthy safety net without dragging in noisy low-quality data.

Priority 3 means this provider only fills fields left N/A by yfinance
(priority 1) and FMP/Finnhub/Polygon (priority 2). The orchestrator's
merge rule (see orchestrator._merge_into) guarantees Stooq never
overwrites a real value from a higher-priority source.
"""
from __future__ import annotations

import logging

from src.collector import price as price_legacy
from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.utils.env import is_env_flag_enabled
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

_STOOQ_HOST = "stooq.com"
_STOOQ_PORT = 443


class StooqProvider(DataProvider):
    """Priority-3 Stooq price fallback.

    Emits only `price` and `change_percent`. On merge, these get used only
    when the primary yfinance source returned None — satisfying the
    "never-regress" guarantee required for graceful degradation.
    """

    name = "stooq"
    provides = {"price"}
    priority = 3
    rate_limit = RateLimit(calls_per_minute=30, burst=10)

    def is_available(self) -> bool:
        if not is_env_flag_enabled("ENABLE_EXTERNAL_FETCH", default=True):
            return False
        return can_open_tcp_connection(_STOOQ_HOST, _STOOQ_PORT)

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        try:
            price, change_percent = price_legacy._fetch_stooq_price_snapshot(ticker)
            if price is None:
                return ProviderResult.failure(self.name, reason="no_stooq_data")

            record_pipeline_event(
                "collector", "info", "data_provider_used",
                ticker=ticker, source=self.name,
            )
            return ProviderResult.success(
                self.name,
                PartialTickerData(
                    ticker=ticker,
                    fields={
                        "price": price,
                        "change_percent": change_percent,
                    },
                ),
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("stooq provider failed for %s", ticker)
            record_pipeline_event(
                "collector", "warning", "ticker_provider_failed",
                ticker=ticker, source=self.name,
                error_type=type(err).__name__, error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")


__all__ = ["StooqProvider"]
