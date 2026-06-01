"""Health checks for monthly summary output artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _load_json_object,
)


_MONTHLY_SUMMARY_STATUSES = {"ok", "no_data", "invalid_json"}


def _validate_monthly_summary_artifact(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    path = root / "monthly_summary.json"
    if not path.exists():
        return ()

    payload = _load_json_object(path)
    required = {"schema_version", "month", "status"}
    if not required.issubset(payload.keys()):
        return (
            OutputHealthIssue(
                "invalid_monthly_summary",
                str(path),
                "missing one of schema_version/month/status",
            ),
        )

    if not _is_non_negative_int(payload.get("schema_version")):
        return (
            OutputHealthIssue(
                "invalid_monthly_summary",
                str(path),
                "schema_version must be a non-negative integer",
            ),
        )
    if not isinstance(payload.get("month"), str) or not payload.get("month", "").strip():
        return (
            OutputHealthIssue(
                "invalid_monthly_summary",
                str(path),
                "month must be a non-empty string",
            ),
        )
    if payload.get("status") not in _MONTHLY_SUMMARY_STATUSES:
        return (
            OutputHealthIssue(
                "invalid_monthly_summary",
                str(path),
                "status must be one of ok/no_data/invalid_json",
            ),
        )
    if payload.get("status") == "ok":
        required_ok_fields = {"trading_days", "start_date", "end_date", "top_tickers", "top_sectors"}
        if not required_ok_fields.issubset(payload.keys()):
            return (
                OutputHealthIssue(
                    "invalid_monthly_summary",
                    str(path),
                    "ok status requires trading_days/start_date/end_date/top_tickers/top_sectors",
                ),
            )
    if "trading_days" in payload and not _is_non_negative_int(payload.get("trading_days")):
        return (
            OutputHealthIssue(
                "invalid_monthly_summary",
                str(path),
                "trading_days must be a non-negative integer",
            ),
        )
    for field in ("start_date", "end_date"):
        if field in payload and not isinstance(payload.get(field), str):
            return (
                OutputHealthIssue(
                    "invalid_monthly_summary",
                    str(path),
                    f"{field} must be a string",
                ),
            )

    top_tickers = payload.get("top_tickers")
    if top_tickers is not None:
        if not isinstance(top_tickers, list):
            return (
                OutputHealthIssue(
                    "invalid_monthly_summary",
                    str(path),
                    "top_tickers must be a list",
                ),
            )
        for index, row in enumerate(top_tickers):
            issue = _validate_monthly_rank_row(path, "top_tickers", index, row, name_field="ticker")
            if issue is not None:
                return (issue,)

    top_sectors = payload.get("top_sectors")
    if top_sectors is not None:
        if not isinstance(top_sectors, list):
            return (
                OutputHealthIssue(
                    "invalid_monthly_summary",
                    str(path),
                    "top_sectors must be a list",
                ),
            )
        for index, row in enumerate(top_sectors):
            issue = _validate_monthly_rank_row(path, "top_sectors", index, row, name_field="sector")
            if issue is not None:
                return (issue,)

    return ()


def _validate_monthly_rank_row(
    path: Path,
    collection: str,
    index: int,
    row: object,
    *,
    name_field: str,
) -> OutputHealthIssue | None:
    required = {name_field, "avg_daily_change"}
    if not isinstance(row, dict) or not required.issubset(row.keys()):
        return OutputHealthIssue(
            "invalid_monthly_summary",
            str(path),
            f"{collection} item {index} missing {name_field}/avg_daily_change",
        )
    for field in (name_field, "avg_daily_change"):
        if not isinstance(row.get(field), str):
            return OutputHealthIssue(
                "invalid_monthly_summary",
                str(path),
                f"{field} must be a string for {collection} item {index}",
            )
    return None
