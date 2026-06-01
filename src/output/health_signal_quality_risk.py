"""Health checks for signal-quality Kelly and turnover panels."""

from __future__ import annotations

from pathlib import Path

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_number_or_none,
    _is_probability,
)


def _validate_signal_kelly(path: Path, payload: dict) -> OutputHealthIssue | None:
    panel = payload.get("kelly")
    if not isinstance(panel, dict):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "kelly must be an object",
        )
    required = {"status", "horizon", "haircut", "by_direction"}
    if not required.issubset(panel.keys()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "kelly missing status/horizon/haircut/by_direction",
        )
    if not isinstance(panel.get("status"), str):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "kelly status must be a string",
        )
    if not _is_non_negative_int(panel.get("horizon")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "horizon must be a non-negative integer for kelly",
        )
    if not _is_probability(panel.get("haircut")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "haircut must be a number from 0 to 1 for kelly",
        )
    by_direction = panel.get("by_direction")
    if not isinstance(by_direction, dict):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "by_direction must be an object for kelly",
        )
    for direction, summary in by_direction.items():
        if not isinstance(direction, str) or not direction.strip():
            return OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                "by_direction keys must be non-empty strings for kelly",
            )
        issue = _validate_signal_kelly_direction(path, direction, summary)
        if issue is not None:
            return issue
    return None


def _validate_signal_kelly_direction(path: Path, direction: str, summary: object) -> OutputHealthIssue | None:
    if not isinstance(summary, dict) or "status" not in summary or "n" not in summary:
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"by_direction {direction} missing status/n for kelly",
        )
    if not isinstance(summary.get("status"), str):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"status must be a string for kelly direction {direction}",
        )
    if not _is_non_negative_int(summary.get("n")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"n must be a non-negative integer for kelly direction {direction}",
        )
    for field in ("hit_rate", "kelly_full", "kelly_half"):
        if field in summary and not _is_probability(summary.get(field)):
            return OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                f"{field} must be a number from 0 to 1 for kelly direction {direction}",
            )
    for field in ("avg_win", "avg_loss", "payoff_ratio"):
        if field in summary and not _is_non_negative_number_or_none(summary.get(field)):
            return OutputHealthIssue(
                "invalid_signal_quality",
                str(path),
                f"{field} must be a non-negative number or null for kelly direction {direction}",
            )
    return None


def _validate_signal_turnover(path: Path, payload: dict) -> OutputHealthIssue | None:
    panel = payload.get("turnover")
    if not isinstance(panel, dict):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "turnover must be an object",
        )
    required = {"status", "sample_size", "points"}
    if not required.issubset(panel.keys()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "turnover missing status/sample_size/points",
        )
    if not isinstance(panel.get("status"), str):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "turnover status must be a string",
        )
    if not _is_non_negative_int(panel.get("sample_size")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "sample_size must be a non-negative integer for turnover",
        )
    if "avg_turnover" in panel and not _is_probability(panel.get("avg_turnover")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "avg_turnover must be a number from 0 to 1 for turnover",
        )
    points = panel.get("points")
    if not isinstance(points, list):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            "points must be a list for turnover",
        )
    for index, point in enumerate(points):
        issue = _validate_signal_turnover_point(path, index, point)
        if issue is not None:
            return issue
    return None


def _validate_signal_turnover_point(path: Path, index: int, point: object) -> OutputHealthIssue | None:
    required = {"date", "tickers", "turnover"}
    if not isinstance(point, dict) or not required.issubset(point.keys()):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"points item {index} missing date/tickers/turnover for turnover",
        )
    if not isinstance(point.get("date"), str) or not point.get("date", "").strip():
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"date must be a non-empty string for turnover points item {index}",
        )
    if not _is_non_negative_int(point.get("tickers")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"tickers must be a non-negative integer for turnover points item {index}",
        )
    if not _is_probability(point.get("turnover")):
        return OutputHealthIssue(
            "invalid_signal_quality",
            str(path),
            f"turnover must be a number from 0 to 1 for turnover points item {index}",
        )
    return None
