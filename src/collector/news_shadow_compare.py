"""Shadow-mode diff between legacy `collect_news_for_watchlist()` and the new
`NewsOrchestrator` path.

Mirrors `src/collector/shadow_compare.py` for the news subsystem. The legacy
`collect_news_for_watchlist` aggregates many sources (Google News RSS,
Reuters/AP/CNBC site-filter feeds, DuckDuckGo search, SEC EDGAR, IR RSS).
The new `NewsOrchestrator` currently only wraps SEC EDGAR + IR RSS providers
— the Google News / DuckDuckGo providers will be ported in later phases.

Why still run a shadow now?
---------------------------
Even with only SEC + IR wrapped, we can validate that:
  * The new providers are called for the same tickers as the legacy path.
  * They return items with the same titles/links for SEC filings and IR
    releases (the subset the orchestrator currently owns).
  * Failures in the new path don't silently hide real data.

When ENABLE_NEWS_ORCHESTRATOR_SHADOW=true, the pipeline runs BOTH paths,
keeps the legacy result as source of truth, and records per-ticker title
diffs (SEC/IR subset only) as pipeline events. Best-effort — exceptions in
the new path never propagate.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from src.collector.news_base import NewsProvider
from src.collector.news_orchestrator import NewsOrchestrator
from src.collector.providers.news.duckduckgo_news_provider import DuckDuckGoNewsProvider
from src.collector.providers.news.google_news_news_provider import GoogleNewsNewsProvider
from src.collector.providers.news.ir_rss_news_provider import IRRSSNewsProvider
from src.collector.providers.news.sec_edgar_news_provider import SECEdgarNewsProvider
from src.types import NewsItem, WatchlistItem
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

# Source tokens the NewsOrchestrator currently owns. Items whose `source`
# field matches one of these are considered part of the diff. Third-party
# sources the orchestrator hasn't ported yet are excluded from the diff.
#
# SEC EDGAR appears verbatim in NewsItem.source.
_SEC_SOURCE_TOKENS: frozenset[str] = frozenset({"sec edgar"})
# Google News + site-filter feeds all surface as these outlet names in the
# legacy pipeline (whatever Google News reported for each item). We include
# them so the diff covers GoogleNewsNewsProvider output too.
_GOOGLE_NEWS_OUTLET_TOKENS: frozenset[str] = frozenset({
    "google news",
    "yahoo finance",
    "reuters",
    "associated press",
    "ap news",
    "cnbc",
    "marketwatch",
    "bloomberg",
})
_DUCKDUCKGO_SOURCE_TOKENS: frozenset[str] = frozenset({"duckduckgo"})
# IR feeds use varied brand names ("Apple Newsroom", "Microsoft Source",
# "NVIDIA Newsroom"…). We match them dynamically per ticker via
# `WatchlistItem.ir_source_names`.

# Log detail cap — beyond this many tickers, we only emit the summary event.
_MAX_DETAILED_DIFFS = 5


def build_news_orchestrator() -> NewsOrchestrator:
    """Construct the shadow-mode NewsOrchestrator with all four providers.

    Kept as its own function so tests and Step 5 primary-mode wiring can
    reuse the same provider list. Registration order mirrors trust tier:
    SEC (priority 4) → IR (2) → Google News (1) → DuckDuckGo (0).
    """
    orchestrator = NewsOrchestrator()
    orchestrator.register_all([
        SECEdgarNewsProvider(),
        IRRSSNewsProvider(),
        GoogleNewsNewsProvider(),
        DuckDuckGoNewsProvider(),
    ])
    return orchestrator


def run_news_shadow_comparison(
    watchlist: list[WatchlistItem],
    run_date: date,
    legacy_news: dict[str, list[NewsItem]],
    *,
    orchestrator: NewsOrchestrator | None = None,
) -> None:
    """Run the NewsOrchestrator in parallel and log the diff. Never raises."""
    try:
        orch = orchestrator or build_news_orchestrator()
        new_news, report = orch.collect_all(watchlist, run_date)
    except Exception as err:  # noqa: BLE001 — shadow must not break pipeline
        logger.exception("Shadow news orchestrator run failed")
        record_pipeline_event(
            "collector", "warning", "news_shadow_orchestrator_failed",
            error_type=type(err).__name__, error_message=str(err),
        )
        return

    _emit_diff_report(watchlist, legacy_news, new_news, report)


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _emit_diff_report(
    watchlist: list[WatchlistItem],
    legacy: dict[str, list[NewsItem]],
    new: dict[str, list[NewsItem]],
    report: Any,
) -> None:
    """Compare per-ticker SEC+IR subsets and emit pipeline events."""
    per_ticker_diffs: list[tuple[str, set[str], set[str]]] = []
    total_missing_in_new = 0
    total_extra_in_new = 0

    for item in watchlist:
        ir_tokens = _ir_tokens_for(item)
        legacy_subset = _extract_owned_titles(legacy.get(item.ticker, []), ir_tokens)
        new_subset = _extract_owned_titles(new.get(item.ticker, []), ir_tokens)

        missing = legacy_subset - new_subset  # in legacy, not in new
        extra = new_subset - legacy_subset    # in new, not in legacy

        if missing or extra:
            per_ticker_diffs.append((item.ticker, missing, extra))
            total_missing_in_new += len(missing)
            total_extra_in_new += len(extra)

    # High-level summary — always emitted.
    record_pipeline_event(
        "collector", "info", "news_shadow_comparison_summary",
        tickers_total=len(watchlist),
        tickers_with_diffs=len(per_ticker_diffs),
        total_missing_in_new=total_missing_in_new,
        total_extra_in_new=total_extra_in_new,
        orchestrator_failures=len(getattr(report, "provider_failures", []) or []),
    )

    # Per-ticker detail — capped.
    for ticker, missing, extra in per_ticker_diffs[:_MAX_DETAILED_DIFFS]:
        if missing:
            record_pipeline_event(
                "collector", "info", "news_shadow_ticker_diff",
                ticker=ticker,
                direction="missing_in_new",
                sample_titles=_sample(missing),
                count=len(missing),
            )
        if extra:
            record_pipeline_event(
                "collector", "info", "news_shadow_ticker_diff",
                ticker=ticker,
                direction="extra_in_new",
                sample_titles=_sample(extra),
                count=len(extra),
            )


def _ir_tokens_for(item: WatchlistItem) -> frozenset[str]:
    """Normalized source-name tokens that identify IR releases for a ticker.

    Legacy `collect_ir_rss_news` may tag items with the brand name from
    `watchlist.yaml` (e.g. "Apple Newsroom"). We collect those values
    lowercased so we can compare apples-to-apples with the orchestrator
    output.
    """
    tokens = {
        str(name).strip().lower()
        for name in (item.ir_source_names or {}).values()
        if str(name).strip()
    }
    # Always include the bare "ir rss" source tag that some legacy items use.
    tokens.add("ir rss")
    return frozenset(tokens)


def _extract_owned_titles(
    items: list[NewsItem],
    ir_tokens: frozenset[str],
) -> set[str]:
    """Return normalized titles for items whose source is owned by one of
    the currently-registered NewsProviders (SEC / IR / Google News / DDG)."""
    owned: set[str] = set()
    for news_item in items:
        source_norm = (news_item.source or "").strip().lower()
        if not source_norm:
            continue
        if not (
            source_norm in _SEC_SOURCE_TOKENS
            or source_norm in ir_tokens
            or source_norm in _GOOGLE_NEWS_OUTLET_TOKENS
            or source_norm in _DUCKDUCKGO_SOURCE_TOKENS
        ):
            continue
        title_norm = _normalize(news_item.title)
        if title_norm:
            owned.add(title_norm)
    return owned


def _normalize(title: str) -> str:
    return " ".join(title.strip().lower().split())


def _sample(titles: set[str], limit: int = 3) -> list[str]:
    """Sorted sample of titles for log readability (determinism for tests)."""
    return sorted(titles)[:limit]


__all__ = [
    "build_news_orchestrator",
    "run_news_shadow_comparison",
]
