"""Base interfaces for the news plugin architecture.

The existing `DataProvider` contract (src/collector/base.py) is shaped
around **scalar ticker fields merged by priority** — great for
price/fundamentals/options, terrible for news. News sources contribute
**lists of items** that should be unioned, deduped, filtered by keyword,
and ranked by source-priority + freshness + catalyst strength. Different
semantics demand a different contract.

This module defines the parallel subsystem:
  * `NewsProvider`   — ABC for a single news source (SEC, IR RSS, Google)
  * `NewsContext`    — per-ticker scratchpad (watchlist item + run_date)
  * `NewsResult`     — success/failure wrapper returning a list[NewsItem]

The `NewsOrchestrator` (see news_orchestrator.py) consumes these to
produce `dict[ticker, list[NewsItem]]`, preserving the output shape
`pipeline.py` already consumes via `collect_news_for_watchlist()`.

Design principles (mirroring DataProvider where possible)
---------------------------------------------------------
* Each provider declares `name` + `source_priority` (higher = more
  trusted source; used for duplicate-title tie-break during merge).
* Providers are side-effect free w.r.t. shared state. Rate limits flow
  through the shared `RateLimiterHub`.
* Never raise — on error, return `NewsResult.failure(reason)` and let
  the orchestrator carry on with the other sources.
* Return `NewsResult.skipped(reason)` when the provider is unavailable
  (no API key, network down, feature flag off). Skipped ≠ failure.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.collector.base import RateLimit
from src.types import NewsItem, WatchlistItem


# ---------------------------------------------------------------------------
# NewsContext — per-ticker input to NewsProvider.collect().
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NewsContext:
    """Context handed to each NewsProvider.collect() call.

    `watchlist_item` carries the per-ticker metadata (CIK, ir_rss_feeds,
    exclude_keywords). Providers read only what they need; the
    orchestrator is the one that decides which providers to call based on
    whether the required fields are set.
    """
    watchlist_item: WatchlistItem
    run_date: date
    # Free-form extras — e.g., shared TCP availability hints passed
    # down from the orchestrator so each provider doesn't re-probe.
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# NewsResult — success/failure/skipped envelope.
# Unlike ProviderResult, data is a list[NewsItem] (not a single dict),
# because news is a union-of-lists semantics, not a priority-merge.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NewsResult:
    """Result envelope returned by NewsProvider.collect()."""
    provider: str
    status: str  # "success" | "failure" | "skipped"
    items: list[NewsItem] = field(default_factory=list)
    reason: str = ""
    latency_ms: int = 0

    @classmethod
    def success(
        cls,
        provider: str,
        items: list[NewsItem],
        latency_ms: int = 0,
    ) -> "NewsResult":
        return cls(provider=provider, status="success", items=items, latency_ms=latency_ms)

    @classmethod
    def failure(cls, provider: str, reason: str, latency_ms: int = 0) -> "NewsResult":
        return cls(provider=provider, status="failure", reason=reason, latency_ms=latency_ms)

    @classmethod
    def skipped(cls, provider: str, reason: str) -> "NewsResult":
        return cls(provider=provider, status="skipped", reason=reason)

    @property
    def ok(self) -> bool:
        return self.status == "success"


# ---------------------------------------------------------------------------
# NewsProvider ABC — the contract every news source implements.
# ---------------------------------------------------------------------------
class NewsProvider(ABC):
    """Abstract base class for news sources.

    Required class attributes:
        name:            Unique identifier (matches config/news_providers.yaml key)
        source_priority: Tie-break score for duplicate headlines during merge.
                         Higher = more trusted. Defaults mirror the legacy
                         source-priority table in news_rss.py (Reuters=5, AP=4,
                         SEC=4, Bloomberg=3, IR=2, etc.).
        rate_limit:      RateLimit for the shared RateLimiterHub.

    Required methods:
        is_available: Called once per pipeline run. Cheap checks (env vars,
                      feature flags, per-item prerequisites like CIK presence).
        collect:      Called once per ticker. MUST NOT raise. Return
                      NewsResult.failure(reason) on error so the orchestrator
                      can keep going with the other providers.
    """

    # Subclasses MUST override these.
    name: str = ""
    source_priority: int = 0
    rate_limit: RateLimit = RateLimit(calls_per_minute=30)

    @abstractmethod
    def is_available(self, ctx: NewsContext) -> bool:
        """Return True if this provider can fetch news for this ticker.

        Providers may inspect `ctx` for per-item prerequisites — e.g.
        the SEC EDGAR provider returns False when `watchlist_item.cik`
        is empty, because it can't look up filings without a CIK.
        """
        ...

    @abstractmethod
    def collect(self, ctx: NewsContext) -> NewsResult:
        """Fetch news items for a single ticker. MUST NOT raise."""
        ...

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<{self.__class__.__name__} name={self.name!r} "
            f"source_priority={self.source_priority}>"
        )


__all__ = [
    "NewsContext",
    "NewsProvider",
    "NewsResult",
]
