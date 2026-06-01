"""Health checks for search audit output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_probability,
    _load_json_object,
)


_SEARCH_AUDIT_VERDICTS = {"info", "pass", "warn"}
_SEARCH_AUDIT_ISSUE_STATUSES = {
    "supported",
    "conflicting",
    "missing_evidence",
    "insufficient_evidence",
}


def _validate_search_audit_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "search_audit.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "date", "generated_at", "source", "tickers", "run_summary"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_search_audit",
                str(path),
                "missing one of schema_version/date/generated_at/source/tickers/run_summary",
            ),
        )

    tickers = payload.get("tickers")
    if not isinstance(tickers, list):
        return (
            OutputHealthIssue(
                "invalid_search_audit",
                str(path),
                "tickers must be a list",
            ),
        )

    run_summary = payload.get("run_summary")
    required_summary_counts = (
        "ticker_count",
        "checked_claims",
        "supported_claims",
        "conflicting_claims",
        "missing_evidence_claims",
        "insufficient_evidence_claims",
        "issue_count",
    )
    if not isinstance(run_summary, dict):
        return (
            OutputHealthIssue(
                "invalid_search_audit",
                str(path),
                "run_summary must be an object",
            ),
        )
    for field in required_summary_counts:
        if not _is_non_negative_int(run_summary.get(field)):
            return (
                OutputHealthIssue(
                    "invalid_search_audit",
                    str(path),
                    f"run_summary {field} must be a non-negative integer",
                ),
            )

    required_ticker_fields = {
        "ticker",
        "verdict",
        "checked_claims",
        "supported_claims",
        "conflicting_claims",
        "missing_evidence_claims",
        "insufficient_evidence_claims",
        "issues",
    }
    ticker_count_fields = (
        "checked_claims",
        "supported_claims",
        "conflicting_claims",
        "missing_evidence_claims",
        "insufficient_evidence_claims",
    )
    required_issue_fields = {
        "claim",
        "field",
        "status",
        "source_url",
        "source_domain",
        "source_title",
        "match_score",
    }
    for index, ticker_payload in enumerate(tickers):
        if not isinstance(ticker_payload, dict) or not required_ticker_fields.issubset(ticker_payload.keys()):
            return (
                OutputHealthIssue(
                    "invalid_search_audit",
                    str(path),
                    f"missing ticker audit fields for item {index}",
                ),
            )

        ticker = str(ticker_payload.get("ticker") or f"item {index}")
        if not isinstance(ticker_payload.get("ticker"), str) or not ticker_payload.get("ticker", "").strip():
            return (
                OutputHealthIssue(
                    "invalid_search_audit",
                    str(path),
                    f"ticker must be a non-empty string for item {index}",
                ),
            )
        if ticker_payload.get("verdict") not in _SEARCH_AUDIT_VERDICTS:
            return (
                OutputHealthIssue(
                    "invalid_search_audit",
                    str(path),
                    f"verdict must be one of info/pass/warn for {ticker}",
                ),
            )
        for field in ticker_count_fields:
            if not _is_non_negative_int(ticker_payload.get(field)):
                return (
                    OutputHealthIssue(
                        "invalid_search_audit",
                        str(path),
                        f"{field} must be a non-negative integer for {ticker}",
                    ),
                )

        issues = ticker_payload.get("issues")
        if not isinstance(issues, list):
            return (
                OutputHealthIssue(
                    "invalid_search_audit",
                    str(path),
                    f"issues must be a list for {ticker}",
                ),
            )
        for issue_index, issue in enumerate(issues):
            if not isinstance(issue, dict) or not required_issue_fields.issubset(issue.keys()):
                return (
                    OutputHealthIssue(
                        "invalid_search_audit",
                        str(path),
                        f"missing issue fields for {ticker} issue {issue_index}",
                    ),
                )
            for field in ("claim", "field", "source_url", "source_domain", "source_title"):
                if not isinstance(issue.get(field), str):
                    return (
                        OutputHealthIssue(
                            "invalid_search_audit",
                            str(path),
                            f"{field} must be a string for {ticker} issue {issue_index}",
                        ),
                    )
            if issue.get("status") not in _SEARCH_AUDIT_ISSUE_STATUSES:
                return (
                    OutputHealthIssue(
                        "invalid_search_audit",
                        str(path),
                        f"status must be one of supported/conflicting/missing_evidence/insufficient_evidence for {ticker} issue {issue_index}",
                    ),
                )
            if not _is_probability(issue.get("match_score")):
                return (
                    OutputHealthIssue(
                        "invalid_search_audit",
                        str(path),
                        f"match_score must be a number from 0 to 1 for {ticker} issue {issue_index}",
                    ),
                )

    return ()
