"""Operational artifact health checks for current-facing output files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.output.health_common import OutputHealthIssue, _load_json_object


_CURRENT_SOURCE_FILES = ("dashboard.json", "dashboard_history.json")
_OPTIONAL_LEGACY_FILES = ("dashboard.json",)


def validate_operational_artifacts(
    *,
    project_root: Path,
    source_root: Path,
    mirror_root: Path,
) -> tuple[tuple[OutputHealthIssue, ...], tuple[OutputHealthIssue, ...]]:
    issues: list[OutputHealthIssue] = []
    warnings: list[OutputHealthIssue] = []
    current_date = _current_source_date(source_root)
    if current_date:
        issues.extend(_source_date_mismatch_issues(source_root, current_date))
        warnings.extend(_web_only_stale_warnings(mirror_root, source_root, current_date))
        issues.extend(_ticker_artifact_issues(project_root, source_root, current_date))
    return tuple(issues), tuple(warnings)


def _current_source_date(source_root: Path) -> str:
    index = _load_json_object(source_root / "index.json")
    value = index.get("date")
    return value if isinstance(value, str) and value else ""


def _source_date_mismatch_issues(source_root: Path, current_date: str) -> list[OutputHealthIssue]:
    issues: list[OutputHealthIssue] = []
    for filename in _CURRENT_SOURCE_FILES:
        path = source_root / filename
        if not path.is_file():
            continue
        artifact_date = _artifact_date(path)
        if not artifact_date:
            issues.append(
                OutputHealthIssue(
                    "source_date_missing",
                    str(path),
                    f"{filename} does not expose a current artifact date",
                )
            )
        elif artifact_date != current_date:
            issues.append(
                OutputHealthIssue(
                    "source_date_mismatch",
                    str(path),
                    f"{filename} date {artifact_date} does not match index date {current_date}",
                )
            )
    return issues


def _web_only_stale_warnings(
    mirror_root: Path,
    source_root: Path,
    current_date: str,
) -> list[OutputHealthIssue]:
    warnings: list[OutputHealthIssue] = []
    for filename in _CURRENT_SOURCE_FILES:
        mirror_path = mirror_root / filename
        source_path = source_root / filename
        if source_path.exists() or not mirror_path.is_file():
            continue
        artifact_date = _artifact_date(mirror_path)
        if not artifact_date:
            warnings.append(
                OutputHealthIssue(
                    "optional_legacy_artifact_present",
                    str(mirror_path),
                    f"{filename} exists only in the web mirror and has no current artifact date",
                )
            )
        elif artifact_date != current_date:
            warnings.append(
                OutputHealthIssue(
                    "web_only_stale_candidate",
                    str(mirror_path),
                    f"{filename} date {artifact_date} does not match index date {current_date}",
                )
            )
        elif filename in _OPTIONAL_LEGACY_FILES:
            warnings.append(
                OutputHealthIssue(
                    "optional_legacy_artifact_present",
                    str(mirror_path),
                    f"{filename} exists only in the web mirror with current date {artifact_date}",
                )
            )
    return warnings


def _artifact_date(path: Path) -> str:
    payload = _load_json_object(path)
    value = payload.get("date")
    if isinstance(value, str) and value:
        return value
    days = payload.get("days")
    if isinstance(days, list) and days:
        last = days[-1]
        if isinstance(last, dict) and isinstance(last.get("date"), str):
            return str(last["date"])
    return ""


def _ticker_artifact_issues(
    project_root: Path,
    source_root: Path,
    current_date: str,
) -> list[OutputHealthIssue]:
    index = _load_json_object(source_root / "index.json")
    issues: list[OutputHealthIssue] = []
    for ticker in _index_tickers(index):
        for path in (
            source_root / "tickers" / ticker / "latest.json",
            source_root / "tickers" / ticker / "history.json",
            project_root / "output" / "tickers" / ticker / f"{current_date}.md",
        ):
            if not path.is_file():
                issues.append(
                    OutputHealthIssue(
                        "ticker_artifact_missing",
                        str(path),
                        f"missing generated artifact for {ticker} on {current_date}",
                    )
                )
    return issues


def _index_tickers(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("tickers")
    if not isinstance(rows, list):
        return []
    tickers: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = row.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            tickers.add(ticker.strip().upper())
    return sorted(tickers)
