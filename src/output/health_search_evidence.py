"""Health checks for search evidence output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_string_list,
    _load_json_object,
)


def _validate_search_evidence_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "search_evidence.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "date", "provider", "items", "by_ticker", "run_summary"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_search_evidence",
                str(path),
                "missing one of schema_version/date/provider/items/by_ticker/run_summary",
            ),
        )

    run_summary = payload.get("run_summary")
    required_cache_summary = {
        "cache_hit_count",
        "cache_error_count",
        "cache_ttl_hours",
        "stale_cache_hit_count",
        "status_counts",
        "priority_refresh_reasons",
        "priority_status_counts",
        "priority_refresh_candidate_count",
    }
    if not isinstance(run_summary, dict) or not required_cache_summary.issubset(run_summary.keys()):
        return (
            OutputHealthIssue(
                "invalid_search_evidence",
                str(path),
                "missing cache summary fields",
            ),
        )
    for field in (
        "cache_hit_count",
        "cache_error_count",
        "cache_ttl_hours",
        "stale_cache_hit_count",
        "priority_refresh_candidate_count",
    ):
        if not _is_non_negative_int(run_summary.get(field)):
            return (
                OutputHealthIssue(
                    "invalid_search_evidence",
                    str(path),
                    f"{field} must be a non-negative integer",
                ),
            )
    for field in ("status_counts", "priority_refresh_reasons", "priority_status_counts"):
        if not _is_non_negative_int_mapping(run_summary.get(field)):
            return (
                OutputHealthIssue(
                    "invalid_search_evidence",
                    str(path),
                    f"{field} must be an object with non-negative integer counts",
                ),
            )

    by_ticker = payload.get("by_ticker")
    required_ticker_summary = {
        "evidence_status",
        "provider_status",
        "priority_for_refresh",
        "priority_refresh_reasons",
        "cache_source_date",
        "cache_age_hours",
    }
    if not isinstance(by_ticker, dict):
        return (
            OutputHealthIssue(
                "invalid_search_evidence",
                str(path),
                "by_ticker must be an object",
            ),
        )
    for ticker, summary in by_ticker.items():
        if not isinstance(summary, dict) or not required_ticker_summary.issubset(summary.keys()):
            return (
                OutputHealthIssue(
                    "invalid_search_evidence",
                    str(path),
                    f"missing ticker summary status/cache fields for {ticker}",
                ),
            )
        string_fields = ("evidence_status", "provider_status", "cache_source_date")
        for field in string_fields:
            if not isinstance(summary.get(field), str):
                return (
                    OutputHealthIssue(
                        "invalid_search_evidence",
                        str(path),
                        f"{field} must be a string for {ticker}",
                    ),
                )
        if not isinstance(summary.get("priority_for_refresh"), bool):
            return (
                OutputHealthIssue(
                    "invalid_search_evidence",
                    str(path),
                    f"priority_for_refresh must be a boolean for {ticker}",
                ),
            )
        if not _is_string_list(summary.get("priority_refresh_reasons")):
            return (
                OutputHealthIssue(
                    "invalid_search_evidence",
                    str(path),
                    f"priority_refresh_reasons must be a list of strings for {ticker}",
                ),
            )
        cache_age_hours = summary.get("cache_age_hours")
        if not isinstance(cache_age_hours, int) or cache_age_hours < 0:
            return (
                OutputHealthIssue(
                    "invalid_search_evidence",
                    str(path),
                    f"cache_age_hours must be a non-negative integer for {ticker}",
                ),
            )

    return ()
