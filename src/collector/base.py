"""Base interfaces for the collector plugin architecture.

This module defines the contract that all data providers must follow:
  - DataProvider: ABC for any data source (yfinance, FMP, Finnhub, etc.)
  - CollectionContext: Per-ticker metadata passed to providers during collect()
  - PartialTickerData: Provider output — partial fields that Orchestrator merges
  - RateLimit: Token bucket configuration (calls per minute)
  - ProviderResult: Success/failure wrapper with provenance

The design principles:
  * Each provider declares `provides` (data types it emits) and `priority`
    (lower wins when multiple providers emit the same field).
  * Providers are side-effect free w.r.t. shared state; rate limiting and
    caching are handled by the Orchestrator, not inside providers.
  * Never raise: providers return ProviderResult.failure(reason) on error.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.types import WatchlistItem


# ---------------------------------------------------------------------------
# Data type taxonomy — providers declare which of these they emit.
# Adding a new data type is purely additive; existing providers unaffected.
# ---------------------------------------------------------------------------
DATA_TYPES: set[str] = {
    "price",
    "fundamentals",
    "technicals",
    "quarterly_financials",
    "upcoming_events",
    "options",
    "insider_transactions",
    "institutional_holdings",
    "analyst_estimates",
    "sec_filings",
    "news",
    "ir_rss",
    "earnings_surprises",
    "historical_prices",
    "sector_rs",
    "social_sentiment",
}


# ---------------------------------------------------------------------------
# RateLimit — shared configuration passed to the central TokenBucketLimiter.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RateLimit:
    """Token bucket rate limit configuration.

    calls_per_minute: Steady-state throughput target.
    burst: Maximum tokens that can accumulate (defaults to calls_per_minute).
    """
    calls_per_minute: int
    burst: int | None = None

    @property
    def effective_burst(self) -> int:
        return self.burst if self.burst is not None else self.calls_per_minute


# ---------------------------------------------------------------------------
# CollectionContext — per-ticker scratchpad. Immutable from the provider's
# view; Orchestrator prepares it before each collect() call.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CollectionContext:
    """Context handed to each provider.collect() call.

    watchlist_item: Full watchlist entry (keywords, CIK, IR feeds, etc.)
    run_date: Pipeline execution date (for cache key + freshness decisions)
    cache_get: Optional callback to fetch cached payload by (provider, key)
    cache_set: Optional callback to store payload with TTL
    rate_limit_wait: Optional callback the provider must await before any
                     outbound HTTP call. Providers that forget to call this
                     are still globally rate-limited by the Orchestrator's
                     wrapping layer, but calling it inside the provider lets
                     slow endpoints delay only their own caller.
    """
    watchlist_item: WatchlistItem
    run_date: date
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PartialTickerData — provider output fragment.
# Orchestrator merges these per ticker into a full CollectedTickerData.
# Only non-None keys are written during merge (preserves higher-priority data).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PartialTickerData:
    """Partial ticker data emitted by a single provider.

    `fields` is a free-form dict whose keys match CollectedTickerData fields.
    Keeping it loosely typed lets new data types flow through without
    requiring a CollectedTickerData schema change every time.

    Providers SHOULD only populate fields listed in their `provides` set, but
    the Orchestrator does not enforce that at runtime (trust-but-log).
    """
    ticker: str
    fields: dict[str, Any] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        return key in self.fields and self.fields[key] is not None


# ---------------------------------------------------------------------------
# ProviderResult — success/failure wrapper with provenance.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProviderResult:
    """Result envelope returned by DataProvider.collect().

    Always use the factory methods (success / failure / skipped) instead of
    constructing directly — they ensure invariants (e.g. data is None on
    failure, reason is empty on success).
    """
    provider: str
    status: str  # "success" | "failure" | "skipped" | "cached"
    data: PartialTickerData | None = None
    reason: str = ""
    latency_ms: int = 0

    @classmethod
    def success(
        cls, provider: str, data: PartialTickerData, latency_ms: int = 0
    ) -> "ProviderResult":
        return cls(provider=provider, status="success", data=data, latency_ms=latency_ms)

    @classmethod
    def failure(cls, provider: str, reason: str, latency_ms: int = 0) -> "ProviderResult":
        return cls(provider=provider, status="failure", reason=reason, latency_ms=latency_ms)

    @classmethod
    def skipped(cls, provider: str, reason: str) -> "ProviderResult":
        return cls(provider=provider, status="skipped", reason=reason)

    @classmethod
    def cached(cls, provider: str, data: PartialTickerData) -> "ProviderResult":
        return cls(provider=provider, status="cached", data=data)

    @property
    def ok(self) -> bool:
        return self.status in ("success", "cached")


# ---------------------------------------------------------------------------
# DataProvider ABC — the contract every data source implements.
# ---------------------------------------------------------------------------
class DataProvider(ABC):
    """Abstract base class for all data sources.

    Required class attributes:
        name: Unique identifier (matches config/providers.yaml key)
        provides: Set of data types this provider emits (subset of DATA_TYPES)
        priority: Lower value wins on conflicts. 1=primary, 2=secondary, 3=fallback
        rate_limit: RateLimit instance (calls per minute)

    Required methods:
        is_available: Called once per pipeline run; returns False if
                      disabled/misconfigured. Should be cheap (env var checks, etc.)
        collect: Called once per ticker. Must never raise — wrap internals
                 in try/except and return ProviderResult.failure on error.
    """

    # Subclasses MUST override these.
    name: str = ""
    provides: set[str] = set()
    priority: int = 99
    rate_limit: RateLimit = RateLimit(calls_per_minute=30)

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can actually run.

        Typical checks:
            - Required env vars present (API keys)
            - Network reachability (optional; orchestrator also probes)
            - Feature flags
        """
        ...

    @abstractmethod
    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        """Fetch data for a single ticker. MUST NOT raise.

        Implementations should:
            1. Short-circuit on unavailability (return ProviderResult.skipped).
            2. Make at most 1 network call per data type in `provides`.
            3. Return ProviderResult.success with only the fields they own.
            4. Catch all exceptions → ProviderResult.failure(reason=str(e)).
        """
        ...

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<{self.__class__.__name__} name={self.name!r} "
            f"priority={self.priority} provides={sorted(self.provides)}>"
        )


__all__ = [
    "DATA_TYPES",
    "CollectionContext",
    "DataProvider",
    "PartialTickerData",
    "ProviderResult",
    "RateLimit",
]
