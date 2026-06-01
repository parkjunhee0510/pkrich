"""Shared contract for output/data -> web/public/output/data mirroring."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator


WEB_SYNC_FILENAMES: tuple[str, ...] = (
    "dashboard_history.json",
    "api_status.json",
    "api_ticker_matrix.json",
    "api_ticker_matrix.csv",
    "analysis_quality.json",
    "validation_warnings.json",
    "cost_log.json",
    "analysis_performance.json",
    "performance_baseline.json",
    "performance_trends.json",
    "quality_reliability_loop.json",
    "routing_outcome.json",
    "direction_alignment.json",
    "ab_test_results.json",
    "price_history.json",
    "ticker_timelines.json",
    "backtest_summary.json",
    "monthly_summary.json",
    "sectors.json",
    "factor_audit.json",
    "signal_quality.json",
    "policy_impact.json",
    "risk_intel_graph.json",
    "risk_intel_summary.json",
    "risk_intel_refresh_log.json",
    "search_evidence.json",
    "search_audit.json",
    "index.json",
)

OPTIONAL_WEB_SYNC_FILENAMES: tuple[str, ...] = (
    "dashboard.json",
)


def iter_web_sync_relative_paths(data_dir: Path) -> Iterator[Path]:
    """Yield source-relative paths that the default web mirror should contain."""
    for filename in (*OPTIONAL_WEB_SYNC_FILENAMES, *WEB_SYNC_FILENAMES):
        path = data_dir / filename
        if path.is_file():
            yield Path(filename)

    tickers_dir = data_dir / "tickers"
    if tickers_dir.is_dir():
        for path in sorted(tickers_dir.rglob("*")):
            if path.is_file():
                yield path.relative_to(data_dir)
