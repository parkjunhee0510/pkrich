"""Alpha Vantage DataProvider — priority-3 fundamentals / earnings fallback.

Alpha Vantage is the last-resort gap-filler. Its free tier caps at 5
calls/minute and 500/day, so we can't afford to use it broadly. Priority 3
ensures it only populates fields that yfinance (p1) and FMP/Finnhub (p2)
left as ``"N/A"``. The orchestrator merge guarantees AV values never
overwrite higher-priority data.

What this provider emits
------------------------
From the bundle returned by ``price._fetch_alpha_vantage_bundle()``:
  * OVERVIEW  → ``market_cap``, ``pe_ratio``, ``eps``, ``week52_high``,
    ``week52_low``, ``sma_50``, ``sma_200``, ``volume``, ``avg_volume_3m``,
    ``price_to_book``, ``dividend_yield``, ``forward_eps``,
    ``earnings_growth``, ``analyst_target_price``
  * INCOME_STATEMENT + EARNINGS → ``quarterly_financials``
    (revenue / operating_income / EPS / estimated EPS / surprise_pct /
    beat_miss classification)
  * EARNINGS + OVERVIEW dividend fields → ``upcoming_events``
    (ex-dividend / dividend-pay / next earnings date)

Intentionally **not** emitted
-----------------------------
``EARNINGS_ESTIMATES`` and ``EARNINGS_CALENDAR`` are fetched by the legacy
bundle helper, but their outputs are only useful when merged against
existing data (e.g., choosing which timing to keep). Since the orchestrator
merge is field-level (not nested-dict-level), we don't pre-merge here —
the priority-based merge handles the gap-fill correctly on its own.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from src.collector import price as price_legacy
from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.utils.network import can_open_tcp_connection
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)

_ALPHA_HOST = "www.alphavantage.co"
_ALPHA_PORT = 443


class AlphaVantageProvider(DataProvider):
    """Priority-3 Alpha Vantage collector — fundamentals/earnings gap-fill."""

    name = "alpha_vantage"
    provides = {
        "fundamentals",
        "quarterly_financials",
        "upcoming_events",
    }
    priority = 3
    # Free tier: 5 cpm, 500/day. Burst=1 so we never queue two calls
    # simultaneously — the legacy module also has its own 12s throttle
    # but the token bucket here protects against future parallel paths.
    rate_limit = RateLimit(calls_per_minute=5, burst=1)

    def is_available(self) -> bool:
        if not os.getenv("ALPHAVANTAGE_API_KEY", "").strip():
            return False
        try:
            return can_open_tcp_connection(_ALPHA_HOST, _ALPHA_PORT, timeout=5)
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        try:
            bundle = price_legacy._fetch_alpha_vantage_bundle(
                ticker,
                include_estimates=True,
                include_calendar=True,
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("alpha_vantage provider failed for %s", ticker)
            record_pipeline_event(
                "collector", "warning", "ticker_provider_failed",
                ticker=ticker, source=self.name,
                error_type=type(err).__name__, error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")

        if not bundle:
            # Rate-limited or API returned nothing usable.
            return ProviderResult.failure(self.name, reason="empty_bundle")

        fields = _build_fields_from_bundle(bundle, ticker, ctx)
        if not _has_any_value(fields):
            return ProviderResult.failure(self.name, reason="empty_extracted")

        record_pipeline_event(
            "collector", "info", "data_provider_used",
            ticker=ticker, source=self.name,
        )
        return ProviderResult.success(
            self.name,
            PartialTickerData(ticker=ticker, fields=fields),
        )


# ---------------------------------------------------------------------------
# Bundle → fields mapping (delegated to legacy helpers)
# ---------------------------------------------------------------------------
def _build_fields_from_bundle(
    bundle: dict[str, Any],
    ticker: str,
    ctx: CollectionContext,
) -> dict[str, Any]:
    """Convert AV bundle into flat fields matching CollectedTickerData names.

    Each extraction is independently try/except-wrapped so a malformed
    sub-response (e.g., invalid OVERVIEW JSON) doesn't kill the other
    extractions.
    """
    fields: dict[str, Any] = {}

    overview = bundle.get("overview") if isinstance(bundle.get("overview"), dict) else {}
    if overview:
        fields.update(_extract_overview_fields(overview))

    # Quarterly financials — list[dict]. Legacy helper already normalizes
    # rows into the schema the downstream analyzer expects.
    try:
        quarterly = price_legacy._extract_alpha_quarterly_financials(bundle)
        if quarterly:
            fields["quarterly_financials"] = quarterly
    except Exception:  # noqa: BLE001
        logger.exception("alpha_vantage quarterly extraction failed for %s", ticker)

    # Upcoming events — list[dict]. Legacy helper handles dates / timing.
    try:
        events = price_legacy._extract_alpha_events(ticker, bundle, ctx.run_date)
        if events:
            fields["upcoming_events"] = events
    except Exception:  # noqa: BLE001
        logger.exception("alpha_vantage events extraction failed for %s", ticker)

    return fields


def _extract_overview_fields(overview: dict[str, Any]) -> dict[str, Any]:
    """Pull the flat OVERVIEW scalars — each defaults to 'N/A' when absent."""
    from src.collector.helpers.formatters import (
        format_growth_percentage as _fmt_growth,
        format_large_number as _fmt_large,
        format_percent_ratio as _fmt_percent,
        format_price as _fmt_price,
        format_ratio as _fmt_ratio,
    )

    out: dict[str, Any] = {}

    # Each of these emits the string "N/A" if the value is missing or bad.
    # We drop the "N/A" here so the merge doesn't log spurious "fills" —
    # only real values propagate.
    mapping: list[tuple[str, Any]] = [
        ("market_cap", _fmt_large(overview.get("MarketCapitalization"))),
        ("pe_ratio", _fmt_ratio(overview.get("PERatio"))),
        ("eps", _fmt_ratio(overview.get("EPS"))),
        ("week52_high", _fmt_ratio(overview.get("52WeekHigh"))),
        ("week52_low", _fmt_ratio(overview.get("52WeekLow"))),
        ("sma_50", _fmt_ratio(overview.get("50DayMovingAverage"))),
        ("sma_200", _fmt_ratio(overview.get("200DayMovingAverage"))),
        ("volume", _fmt_large(overview.get("Volume"))),
        ("avg_volume_3m", _fmt_large(overview.get("AverageVolume"))),
        ("price_to_book", _fmt_ratio(overview.get("PriceToBookRatio"))),
        ("dividend_yield", _fmt_percent(overview.get("DividendYield"))),
        ("forward_eps", _fmt_ratio(overview.get("ForwardEPS"))),
        ("earnings_growth", _fmt_growth(overview.get("QuarterlyEarningsGrowthYOY"))),
        # Analyst target price in USD — currency inferred elsewhere.
        ("analyst_target_price", _fmt_price(overview.get("AnalystTargetPrice"), "USD")),
    ]

    for key, value in mapping:
        if value and value != "N/A":
            out[key] = value
    return out


def _has_any_value(fields: dict[str, Any]) -> bool:
    for value in fields.values():
        if value in (None, "", "N/A"):
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return True
    return False


__all__ = ["AlphaVantageProvider"]
