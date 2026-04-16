"""Shadow-mode diff between legacy `collect_market_data()` and the new
`CollectionOrchestrator` path.

Purpose
-------
Phase 1-0e Step 3 ships the orchestrator alongside (not instead of) the
existing collection code. When `ENABLE_ORCHESTRATOR_SHADOW=true`, the
pipeline runs BOTH paths, uses the legacy result as source of truth, and
records per-field differences as pipeline events so we can validate the new
architecture before cutting over in Step 5.

This module is intentionally side-effect free other than logging:
    * No pipeline state is mutated.
    * Orchestrator exceptions never propagate — shadow mode is best-effort.
    * Log volume is capped (top N differing tickers) to avoid spam.

Fields compared
---------------
Only yfinance-owned fields are compared at this stage because the yfinance
provider is the only one extracted so far. FMP / Finnhub / etc. fields are
still populated exclusively by the legacy path.
"""
from __future__ import annotations

import logging
from dataclasses import fields as dc_fields
from datetime import date
from typing import Any

from src.collector.orchestrated_collection import build_full_orchestrator
from src.types import CollectedTickerData, WatchlistItem
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

# Fields the yfinance provider currently owns. Only these are diffed —
# comparing anything else would produce noise from providers not yet ported.
_YFINANCE_OWNED_FIELDS: frozenset[str] = frozenset({
    "price",
    "change_percent",
    "currency",
    "market_cap",
    "pe_ratio",
    "eps",
    "week52_high",
    "week52_low",
    "sma_50",
    "sma_200",
    "volume",
    "avg_volume_3m",
    "price_to_book",
    "dividend_yield",
    "forward_eps",
    "earnings_growth",
    "short_float_pct",
    "short_ratio",
    "analyst_target_price",
    "analyst_recommendation",
    "analyst_count",
    "held_by_insiders",
    "held_by_institutions",
    "implied_volatility",
    "price_change_7d",
    "price_change_30d",
    "atr_14d",
    "atr_percent",
    "relative_volume",
    "gap_percent",
    "price_vs_sma50",
    "price_vs_sma200",
    "week52_position",
    "rs_vs_spy",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "day_volume",
})

# Max tickers whose per-field diffs are logged in detail. Beyond this, only
# summary counts are emitted (to avoid flooding logs on a large watchlist).
_MAX_DETAILED_DIFFS = 5


def run_shadow_comparison(
    watchlist: list[WatchlistItem],
    run_date: date,
    legacy_collected: dict[str, CollectedTickerData],
    benchmark_change_30d: float | None = None,
) -> None:
    """Run the orchestrator path in parallel and log the diff. Never raises."""
    try:
        orchestrator = build_full_orchestrator(
            benchmark_change_30d=benchmark_change_30d,
        )
        new_collected, report = orchestrator.collect_all(watchlist, run_date)
    except Exception as err:  # noqa: BLE001 — shadow must not break pipeline
        logger.exception("Shadow orchestrator run failed")
        record_pipeline_event(
            "collector", "warning", "shadow_orchestrator_failed",
            error_type=type(err).__name__, error_message=str(err),
        )
        return

    _emit_diff_report(legacy_collected, new_collected, report)


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _emit_diff_report(
    legacy: dict[str, CollectedTickerData],
    new: dict[str, CollectedTickerData],
    report: Any,
) -> None:
    """Compare per-ticker outputs and emit pipeline events."""
    total_tickers = len(legacy)
    tickers_with_diffs: list[tuple[str, list[tuple[str, Any, Any]]]] = []
    total_field_diffs = 0

    for ticker, legacy_data in legacy.items():
        new_data = new.get(ticker)
        if new_data is None:
            # Orchestrator didn't produce output for this ticker (provider
            # was unavailable or everything failed) — don't treat as diff,
            # just note it.
            record_pipeline_event(
                "collector", "info", "shadow_ticker_missing",
                ticker=ticker,
            )
            continue

        diffs = _diff_ticker(legacy_data, new_data)
        if diffs:
            tickers_with_diffs.append((ticker, diffs))
            total_field_diffs += len(diffs)

    # High-level summary event — always emitted.
    record_pipeline_event(
        "collector", "info", "shadow_comparison_summary",
        tickers_total=total_tickers,
        tickers_with_diffs=len(tickers_with_diffs),
        total_field_diffs=total_field_diffs,
        orchestrator_failures=report.failure_count() if report else 0,
    )

    # Per-ticker detail — capped to keep log volume sane.
    for ticker, diffs in tickers_with_diffs[:_MAX_DETAILED_DIFFS]:
        for field, legacy_val, new_val in diffs:
            record_pipeline_event(
                "collector", "info", "shadow_field_diff",
                ticker=ticker,
                field=field,
                legacy=_truncate(legacy_val),
                orchestrator=_truncate(new_val),
            )


def _diff_ticker(
    legacy: CollectedTickerData,
    new: CollectedTickerData,
) -> list[tuple[str, Any, Any]]:
    """Return list of (field_name, legacy_value, new_value) that differ.

    Only compares yfinance-owned fields. Values are normalized before diff:
      * "N/A" == "" == None — all treated as "missing"
      * Floats compared with a small relative tolerance (API rounding)
    """
    diffs: list[tuple[str, Any, Any]] = []
    legacy_field_names = {f.name for f in dc_fields(legacy)}

    for fname in _YFINANCE_OWNED_FIELDS:
        if fname not in legacy_field_names:
            continue
        a = getattr(legacy, fname, None)
        b = getattr(new, fname, None)
        if not _values_match(a, b):
            diffs.append((fname, a, b))
    return diffs


def _values_match(a: Any, b: Any) -> bool:
    """Compare two field values with domain-aware tolerance."""
    a_norm = _normalize_missing(a)
    b_norm = _normalize_missing(b)
    if a_norm is None and b_norm is None:
        return True
    if a_norm is None or b_norm is None:
        return False
    # Numeric tolerance: API responses can differ by last decimal place.
    if isinstance(a_norm, (int, float)) and isinstance(b_norm, (int, float)):
        return abs(a_norm - b_norm) <= max(0.01, abs(a_norm) * 0.001)
    return str(a_norm) == str(b_norm)


def _normalize_missing(value: Any) -> Any:
    """Collapse N/A / empty-string / None to None for comparison."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "N/A", "n/a"):
        return None
    return value


def _truncate(value: Any, limit: int = 60) -> str:
    """Safe string form for logging."""
    s = repr(value)
    return s if len(s) <= limit else s[: limit - 3] + "..."


__all__ = ["run_shadow_comparison"]
