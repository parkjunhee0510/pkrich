"""Per-ticker derivations computed once, consumed by output/ serializers."""
from __future__ import annotations

from typing import Any

from src.types import TickerAnalysis
from src.utils.earnings_history import build_earnings_surprise_summary
from src.utils.earnings_pattern import build_earnings_pattern
from src.utils.earnings_setup import build_earnings_setup
from src.utils.sec_filings import (
    collect_sec_filing_tags,
    collect_sec_filings,
    sort_sec_filings,
)


def _snapshot_currency(snapshot: dict[str, str]) -> str:
    price_value = str(snapshot.get("Price", "")).strip()
    if not price_value:
        return "USD"
    parts = price_value.split()
    if len(parts) >= 2 and parts[-1].isalpha():
        return parts[-1]
    return "USD"


def build_ticker_derivations(analysis: TickerAnalysis) -> dict[str, Any]:
    currency = _snapshot_currency(analysis.data_snapshot)
    return {
        "earnings_setup": build_earnings_setup(
            analysis.fundamentals,
            analysis.quarterly_financials,
            analysis.upcoming_events,
            currency=currency,
        ),
        "earnings_surprise_history": build_earnings_surprise_summary(analysis.quarterly_financials),
        "earnings_pattern": build_earnings_pattern(analysis.quarterly_financials),
        "sec_filing_tags": collect_sec_filing_tags(analysis.news_references),
        "sec_filings": sort_sec_filings(collect_sec_filings(analysis.news_references)),
    }


def build_derivations_by_ticker(analyses: list[TickerAnalysis]) -> dict[str, dict[str, Any]]:
    return {analysis.ticker: build_ticker_derivations(analysis) for analysis in analyses}
