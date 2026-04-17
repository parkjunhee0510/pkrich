"""NewsOrchestrator — runs all registered NewsProviders per ticker and
merges their output into the shape `pipeline.py` already consumes:
``dict[ticker, list[NewsItem]]``.

Why is this not the main `CollectionOrchestrator`?
---------------------------------------------------
News has fundamentally different merge semantics:

  * DataProvider merge  — priority-based overwrite, scalar-level
                          ("yfinance wins over Alpha Vantage on EPS")
  * NewsProvider merge  — union-of-lists, dedup-by-title, then rank
                          by source_priority × freshness × exclusion

Rather than overload CollectionOrchestrator with two merge strategies
and risk subtle bugs ("which priority applies to which field?"), we run
a parallel orchestrator. Both share the `RateLimiterHub` infrastructure
and can share an `ResponseCache` if we later decide to cache RSS feeds.

Runtime model
-------------
For each ticker:
  1. Filter to NewsProviders whose `is_available(ctx)` returns True.
  2. For each provider, acquire a rate-limit token, then `collect(ctx)`.
  3. Union the resulting items across providers.
  4. Apply exclude_keywords filter.
  5. Dedup by normalized title (keep the higher source_priority copy).
  6. Rank by `(source_priority, freshness, catalyst_score)` descending.
  7. Truncate to `max_items_per_ticker`.

Ranking, dedup, and catalyst scoring are intentionally kept in this
module — not in providers — so they remain orthogonal to the data
source. A provider only knows how to fetch; the orchestrator decides
how those fetches compose into the final shown-to-user list.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

from src.collector.news_base import NewsContext, NewsProvider
from src.collector.rate_limiter import RateLimiterHub
from src.types import NewsItem, WatchlistItem
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)


# Default max headlines per ticker after merge/rank/truncate.
_DEFAULT_MAX_ITEMS_PER_TICKER = 5

# A single token-acquire wait budget. The pipeline is sync today, so a
# 30s ceiling is generous. Phase 1-1 parallelization can lower this.
_RATE_LIMIT_WAIT_SECONDS = 30.0


# ---------------------------------------------------------------------------
# NewsCollectionReport — observability output so pipeline.py can log totals.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NewsCollectionReport:
    """Summary of one NewsOrchestrator.collect_all() run."""
    per_ticker_counts: dict[str, int] = field(default_factory=dict)
    per_provider_counts: dict[str, int] = field(default_factory=dict)
    provider_failures: list[tuple[str, str, str]] = field(default_factory=list)  # (provider, ticker, reason)

    def total_items(self) -> int:
        return sum(self.per_ticker_counts.values())


# ---------------------------------------------------------------------------
# NewsOrchestrator
# ---------------------------------------------------------------------------
class NewsOrchestrator:
    """Runs NewsProviders per ticker and merges into dict[ticker, list[NewsItem]].

    Thread-safety: `collect_all()` is intentionally sequential for now
    (matches legacy behavior). When Phase 1-1 parallelizes, only the
    per-ticker loop needs a ThreadPoolExecutor — the rate_limiter hub
    is already thread-safe.
    """

    def __init__(
        self,
        rate_hub: RateLimiterHub | None = None,
        *,
        max_items_per_ticker: int = _DEFAULT_MAX_ITEMS_PER_TICKER,
    ) -> None:
        self._providers: list[NewsProvider] = []
        self._rate_hub = rate_hub or RateLimiterHub()
        self._max_items_per_ticker = max_items_per_ticker

    # -- registration --------------------------------------------------
    def register(self, provider: NewsProvider) -> None:
        if not provider.name:
            raise ValueError(f"NewsProvider {provider!r} has no name")
        self._providers.append(provider)
        self._rate_hub.register(provider.name, provider.rate_limit)

    def register_all(self, providers: Iterable[NewsProvider]) -> None:
        for provider in providers:
            self.register(provider)

    @property
    def providers(self) -> list[NewsProvider]:
        return list(self._providers)

    # -- collection ----------------------------------------------------
    def collect_all(
        self,
        watchlist: list[WatchlistItem],
        run_date: date,
        *,
        context_extra: dict[str, object] | None = None,
    ) -> tuple[dict[str, list[NewsItem]], NewsCollectionReport]:
        """Fetch and merge news for every ticker in the watchlist."""
        per_ticker: dict[str, list[NewsItem]] = {}
        report = NewsCollectionReport()
        per_ticker_counts: dict[str, int] = {}
        per_provider_counts: dict[str, int] = {}
        provider_failures: list[tuple[str, str, str]] = []

        for item in watchlist:
            ctx = NewsContext(
                watchlist_item=item,
                run_date=run_date,
                extra=dict(context_extra or {}),
            )
            items = self._collect_for_ticker(
                ctx, per_provider_counts, provider_failures
            )
            merged = self._merge_and_rank(items, item, run_date)
            per_ticker[item.ticker] = merged
            per_ticker_counts[item.ticker] = len(merged)

        return per_ticker, NewsCollectionReport(
            per_ticker_counts=per_ticker_counts,
            per_provider_counts=per_provider_counts,
            provider_failures=provider_failures,
        )

    # -- per-ticker orchestration -------------------------------------
    def _collect_for_ticker(
        self,
        ctx: NewsContext,
        per_provider_counts: dict[str, int],
        provider_failures: list[tuple[str, str, str]],
    ) -> list[tuple[NewsItem, int]]:
        """Returns items paired with provider source_priority for later dedup."""
        all_items: list[tuple[NewsItem, int]] = []

        for provider in self._providers:
            try:
                if not provider.is_available(ctx):
                    continue
            except Exception as err:  # noqa: BLE001 — is_available must not kill the loop
                logger.exception(
                    "NewsProvider %s is_available raised", provider.name
                )
                provider_failures.append(
                    (provider.name, ctx.watchlist_item.ticker, f"is_available:{err}")
                )
                continue

            acquired = self._rate_hub.acquire(
                provider.name, timeout=_RATE_LIMIT_WAIT_SECONDS
            )
            if not acquired:
                # Rate-limit starvation — rare in sync mode, but log it.
                provider_failures.append(
                    (provider.name, ctx.watchlist_item.ticker, "rate_limit_timeout")
                )
                continue

            start = time.monotonic()
            try:
                result = provider.collect(ctx)
            except Exception as err:  # noqa: BLE001
                logger.exception(
                    "NewsProvider %s.collect() raised (contract violation)",
                    provider.name,
                )
                provider_failures.append(
                    (provider.name, ctx.watchlist_item.ticker, f"exception:{err}")
                )
                continue

            latency_ms = int((time.monotonic() - start) * 1000)

            if result.status == "skipped":
                continue
            if result.status == "failure":
                provider_failures.append(
                    (provider.name, ctx.watchlist_item.ticker, result.reason)
                )
                record_pipeline_event(
                    "collector", "warning", "news_provider_failed",
                    ticker=ctx.watchlist_item.ticker,
                    source=provider.name,
                    error_message=result.reason,
                    latency_ms=latency_ms,
                )
                continue

            per_provider_counts[provider.name] = (
                per_provider_counts.get(provider.name, 0) + len(result.items)
            )
            all_items.extend((item, provider.source_priority) for item in result.items)
            record_pipeline_event(
                "collector", "info", "news_provider_completed",
                ticker=ctx.watchlist_item.ticker,
                source=provider.name,
                result_count=len(result.items),
                latency_ms=latency_ms,
            )

        return all_items

    # -- merge / dedup / rank -----------------------------------------
    def _merge_and_rank(
        self,
        items_with_priority: list[tuple[NewsItem, int]],
        watchlist_item: WatchlistItem,
        run_date: date,
    ) -> list[NewsItem]:
        """Union → exclude-keyword filter → dedup-by-title → rank → truncate."""
        if not items_with_priority:
            return []

        filtered = [
            (item, priority)
            for item, priority in items_with_priority
            if not _matches_excluded(item, watchlist_item.exclude_keywords)
        ]
        if not filtered:
            return []

        deduped = _dedup_by_title(filtered)
        ranked = sorted(
            deduped,
            key=lambda pair: _rank_key(pair[0], pair[1], run_date),
            reverse=True,
        )
        return [item for item, _priority in ranked[: self._max_items_per_ticker]]


# ---------------------------------------------------------------------------
# Pure helpers (deterministic, unit-testable without the orchestrator)
# ---------------------------------------------------------------------------
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    return _WHITESPACE_RE.sub(" ", title.strip().lower())


def _matches_excluded(item: NewsItem, exclude_keywords: list[str]) -> bool:
    if not exclude_keywords:
        return False
    title_lower = item.title.lower()
    return any(kw.lower() in title_lower for kw in exclude_keywords if kw)


def _dedup_by_title(
    items_with_priority: list[tuple[NewsItem, int]],
) -> list[tuple[NewsItem, int]]:
    """Keep one copy per normalized title — the one with highest priority."""
    best: dict[str, tuple[NewsItem, int]] = {}
    for item, priority in items_with_priority:
        key = _normalize_title(item.title)
        if not key:
            continue
        current = best.get(key)
        if current is None or priority > current[1]:
            best[key] = (item, priority)
    return list(best.values())


def _rank_key(
    item: NewsItem, source_priority: int, run_date: date
) -> tuple[int, float, int]:
    """Rank key — higher is better. Composed of:

    1. `source_priority` — Reuters beats a random blog.
    2. Freshness score   — linear decay over ~30 days.
    3. Catalyst hint     — SEC tag match nudges upward.
    """
    age_days = _age_in_days(item.published_at, run_date)
    freshness = max(0.0, 30.0 - age_days) if age_days is not None else 0.0
    catalyst = 1 if _looks_like_catalyst(item) else 0
    return (source_priority, freshness, catalyst)


def _age_in_days(published_at: str, run_date: date) -> float | None:
    if not published_at:
        return None
    try:
        # RFC 2822 (RSS default)
        dt = parsedate_to_datetime(published_at)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    run_dt = datetime(run_date.year, run_date.month, run_date.day, tzinfo=timezone.utc)
    delta = (run_dt - dt).total_seconds() / 86400.0
    return max(0.0, delta)


_CATALYST_HINTS = ("earnings", "guidance", "8-K", "10-Q", "10-K", "upgrade", "downgrade")


def _looks_like_catalyst(item: NewsItem) -> bool:
    haystack = f"{item.title} {item.source}".lower()
    return any(hint.lower() in haystack for hint in _CATALYST_HINTS)


__all__ = [
    "NewsCollectionReport",
    "NewsOrchestrator",
    "_age_in_days",
    "_dedup_by_title",
    "_matches_excluded",
    "_normalize_title",
    "_rank_key",
]
