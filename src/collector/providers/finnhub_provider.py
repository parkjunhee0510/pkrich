"""Finnhub DataProvider — priority-2 analyst recommendation trend source.

Finnhub's free tier (60 calls/min) is narrow but high-quality for two things
the other providers don't cover well:
  * Analyst recommendation trends (strong_buy/buy/hold/sell/strong_sell
    counts, with a computed `trend` field — upgrading/downgrading/stable)
  * (Future) Earnings calendar + peers, already exposed by the legacy
    module but not yet consumed by the orchestrator path

Scope for this provider is intentionally limited to `recommendation_trends`
so the merge semantics stay predictable. Economic calendar + earnings
calendar + peers stay in the legacy collector until we refactor the
pipeline-level aggregates (those are not per-ticker tape data).

Priority 2: fills gaps in the analyst fields yfinance emits — yfinance
has the single-score `recommendationMean`, while Finnhub gives the
full 6-month rolling distribution.
"""
from __future__ import annotations

import logging

from src.collector import finnhub as finnhub_module
from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)


class FinnhubProvider(DataProvider):
    """Priority-2 Finnhub collector — analyst recommendation trends."""

    name = "finnhub"
    provides = {"recommendation_trends"}
    priority = 2
    # Finnhub free tier: 60 cpm hard cap. Keep burst small so a watchlist
    # sweep doesn't burn the entire minute in one breath.
    rate_limit = RateLimit(calls_per_minute=55, burst=10)

    def is_available(self) -> bool:
        try:
            return finnhub_module.is_finnhub_ready()
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        try:
            trends = finnhub_module.collect_finnhub_recommendations(ticker)
        except Exception as err:  # noqa: BLE001
            logger.exception("finnhub provider failed for %s", ticker)
            record_pipeline_event(
                "collector", "warning", "ticker_provider_failed",
                ticker=ticker, source=self.name,
                error_type=type(err).__name__, error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")

        if not trends:
            # Not an error — many tickers genuinely have no coverage.
            return ProviderResult.failure(self.name, reason="no_recommendations")

        record_pipeline_event(
            "collector", "info", "data_provider_used",
            ticker=ticker, source=self.name,
        )
        return ProviderResult.success(
            self.name,
            PartialTickerData(
                ticker=ticker,
                fields={"recommendation_trends": trends},
            ),
        )


__all__ = ["FinnhubProvider"]
