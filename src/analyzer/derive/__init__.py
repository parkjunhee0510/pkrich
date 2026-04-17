"""Derivation layer — pure post-collection transformations.

Re-exports builders that turn collected/analyzed data into derived artifacts
(summaries, timelines, score rollups). Call these from the orchestration
layer (pipeline/markdown) and pass results into output/ as kwargs, so the
output layer remains write-only.
"""

from __future__ import annotations

from src.backtester.engine import build_backtest_summary
from src.utils.earnings_history import build_earnings_surprise_summary
from src.utils.earnings_pattern import build_earnings_pattern
from src.utils.earnings_setup import build_earnings_setup
from src.utils.monthly_summary import load_monthly_summary
from src.utils.sec_filings import (
    collect_sec_filing_tags,
    collect_sec_filings,
    sort_sec_filings,
)
from src.analyzer.derive.ticker import build_derivations_by_ticker, build_ticker_derivations
from src.utils.ticker_timelines import build_ticker_timelines
from src.utils.weekly_summary import WeeklySummaryData, load_weekly_summary

__all__ = [
    "build_derivations_by_ticker",
    "build_ticker_derivations",
    "build_backtest_summary",
    "build_earnings_surprise_summary",
    "build_earnings_pattern",
    "build_earnings_setup",
    "load_monthly_summary",
    "collect_sec_filing_tags",
    "collect_sec_filings",
    "sort_sec_filings",
    "build_ticker_timelines",
    "WeeklySummaryData",
    "load_weekly_summary",
]
