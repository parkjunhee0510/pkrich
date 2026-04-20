"""FMP (Financial Modeling Prep) DataProvider ??priority-2 enrichment source.

FMP supplies the "2nd opinion" data that yfinance doesn't carry well:
  * Analyst estimate revisions (30d / 90d trend + direction)
  * Insider transactions (buy/sell summary)
  * Institutional holder changes (concentration shifts)
  * Earnings surprises history (FMP flavour, complements yfinance)
  * Key metrics & financial ratios (margins, ROIC, etc.)
  * Dividend history
  * Company profile (sector/industry fallback)

Design notes
------------
* FMP's free tier caps at 250 calls/day ??each ticker consumes up to ~6
  endpoints here. Orchestrator's cache (24h TTL on fundamentals) is what
  keeps daily quota manageable.
* `should_collect_fmp_extended()` gates the higher-volume endpoints
  (insider, institutional, estimate revisions, surprises). When disabled,
  only the cheap core endpoints run.
* Priority 2: fills gaps left by yfinance, loses to yfinance when both
  cover the same field.
"""
from __future__ import annotations

import logging
from typing import Any

from src.collector import fmp as fmp_module
from src.collector.base import (
    CollectionContext,
    DataProvider,
    PartialTickerData,
    ProviderResult,
    RateLimit,
)
from src.utils.pipeline_logging import record_pipeline_event

logger = logging.getLogger(__name__)


class FMPProvider(DataProvider):
    """Priority-2 FMP collector for analyst / insider / institutional data."""

    name = "fmp"
    provides = {
        "fundamentals",
        "analyst_estimates",
        "insider_transactions",
        "institutional_holdings",
        "earnings_surprises",
    }
    priority = 2
    rate_limit = RateLimit(calls_per_minute=300, burst=20)

    def is_available(self) -> bool:
        # is_fmp_ready() checks both API key and TCP reachability.
        try:
            return fmp_module.is_fmp_ready()
        except Exception:  # noqa: BLE001
            return False

    def collect(self, ticker: str, ctx: CollectionContext) -> ProviderResult:
        try:
            fields = self._collect_fields(ticker, ctx)
            if not _has_any_value(fields):
                return ProviderResult.failure(self.name, reason="empty_response")

            record_pipeline_event(
                "collector", "info", "data_provider_used",
                ticker=ticker, source=self.name,
            )
            return ProviderResult.success(
                self.name,
                PartialTickerData(ticker=ticker, fields=fields),
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("fmp provider failed for %s", ticker)
            record_pipeline_event(
                "collector", "warning", "ticker_provider_failed",
                ticker=ticker, source=self.name,
                error_type=type(err).__name__, error_message=str(err),
            )
            return ProviderResult.failure(self.name, reason=f"exception:{err}")

    # ---------------------------------------------------------------
    # internals
    # ---------------------------------------------------------------
    def _collect_fields(self, ticker: str, ctx: CollectionContext) -> dict[str, Any]:
        """Assemble FMP field payload. Each endpoint is independently try/except-wrapped."""
        out: dict[str, Any] = {}
        extended = _safe(fmp_module.should_collect_fmp_extended, default=False)

        # Core (always attempted) ??key metrics, ratios, dividends, profile.
        metrics = _safe_dict(fmp_module.collect_fmp_key_metrics, ticker)
        metrics.update(_safe_dict(fmp_module.collect_fmp_financial_ratios, ticker))
        dividends = _safe_dict(fmp_module.collect_fmp_dividend_history, ticker)
        if dividends:
            metrics.update(dividends)

        profile = _safe_dict(fmp_module.collect_fmp_company_profile, ticker)
        if profile:
            if "industry" in profile:
                metrics["industry"] = profile["industry"]
            if "beta" in profile:
                metrics["beta"] = profile["beta"]
            # `sector` goes to CollectedTickerData.sector ??only fill gaps.
            if profile.get("sector"):
                out["sector"] = profile["sector"]

        if metrics:
            out["fundamental_metrics"] = metrics

        # Extended (gated) ??per-ticker call cost is meaningful.
        if extended:
            revisions = _safe_dict(fmp_module.collect_fmp_analyst_estimates, ticker, ctx.run_date)
            if revisions:
                out["analyst_estimate_revisions"] = revisions

            insiders = _safe_list(fmp_module.collect_fmp_insider_trading, ticker, ctx.run_date)
            if insiders:
                out["insider_transactions"] = insiders

            institutional = _safe_dict(fmp_module.collect_fmp_institutional_holders, ticker)
            if institutional:
                out["institutional_changes"] = institutional

            surprises = _safe_list(fmp_module.collect_fmp_earnings_surprises, ticker)
            if surprises:
                out["fmp_earnings_surprises"] = surprises

        return out


# ---------------------------------------------------------------------------
# Defensive helpers ??FMP endpoints occasionally throw on quota/404; wrap them.
# ---------------------------------------------------------------------------
def _safe(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        return default


def _safe_dict(fn, *args, **kwargs) -> dict[str, Any]:
    result = _safe(fn, *args, default=None, **kwargs)
    return result if isinstance(result, dict) else {}


def _safe_list(fn, *args, **kwargs) -> list[Any]:
    result = _safe(fn, *args, default=None, **kwargs)
    return result if isinstance(result, list) else []


def _has_any_value(fields: dict[str, Any]) -> bool:
    """Return True if the payload has at least one non-empty field."""
    for value in fields.values():
        if value in (None, "", "N/A"):
            continue
        if isinstance(value, (dict, list)) and not value:
            continue
        return True
    return False


__all__ = ["FMPProvider"]

