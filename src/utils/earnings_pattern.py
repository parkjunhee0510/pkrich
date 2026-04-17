"""Structured earnings surprise pattern analysis from quarterly financials."""
from __future__ import annotations

import re
from typing import Literal

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")

SurpriseTrend = Literal["improving", "deteriorating", "stable", "insufficient_data"]


def build_earnings_pattern(quarterly_financials: list[dict[str, str]]) -> dict[str, int | str]:
    """Build earnings surprise pattern summary from the latest four quarters."""
    recent_rows = quarterly_financials[:4]
    beat_streak = _count_beat_streak(recent_rows)
    surprise_values = _extract_surprise_values(recent_rows)
    trend = _classify_surprise_trend(surprise_values)
    avg_surprise = _format_average_surprise(surprise_values)
    quarters_analyzed = len(surprise_values)

    return {
        "beat_streak": beat_streak,
        "surprise_trend": trend,
        "avg_surprise_pct": avg_surprise,
        "quarters_analyzed": quarters_analyzed,
        "pattern_note": _build_pattern_note(beat_streak, trend, avg_surprise, quarters_analyzed),
    }


def _count_beat_streak(rows: list[dict[str, str]]) -> int:
    streak = 0
    for row in rows:
        beat_miss = str(row.get("beat_miss", "")).strip().lower()
        if beat_miss == "beat":
            streak += 1
            continue
        break
    return streak


def _extract_surprise_values(rows: list[dict[str, str]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        parsed = _parse_percent(row.get("surprise_pct", "N/A"))
        if parsed is not None:
            values.append(parsed)
    return values


def _classify_surprise_trend(values: list[float]) -> SurpriseTrend:
    if len(values) <= 2:
        return "insufficient_data"

    oldest_to_latest = list(reversed(values))
    points = len(oldest_to_latest)
    x_mean = (points - 1) / 2
    y_mean = sum(oldest_to_latest) / points
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(oldest_to_latest))
    denominator = sum((index - x_mean) ** 2 for index in range(points))
    slope = numerator / denominator if denominator else 0.0

    if slope >= 1.0:
        return "improving"
    if slope <= -1.0:
        return "deteriorating"
    return "stable"


def _format_average_surprise(values: list[float]) -> str:
    if not values:
        return "N/A"
    average = sum(values) / len(values)
    return f"{average:+.1f}%"


def _build_pattern_note(
    beat_streak: int,
    trend: SurpriseTrend,
    avg_surprise_pct: str,
    quarters_analyzed: int,
) -> str:
    parts: list[str] = []
    if beat_streak > 0:
        parts.append(f"최근 {beat_streak}개 분기 연속 상회")

    trend_labels = {
        "improving": f"최근 {quarters_analyzed}개 분기 서프라이즈 추세 개선",
        "deteriorating": f"최근 {quarters_analyzed}개 분기 서프라이즈 추세 악화",
        "stable": f"최근 {quarters_analyzed}개 분기 서프라이즈 추세 안정",
        "insufficient_data": "서프라이즈 추세 판단용 데이터 부족",
    }
    parts.append(trend_labels[trend])

    if avg_surprise_pct != "N/A":
        parts.append(f"평균 서프라이즈 {avg_surprise_pct}")

    return " · ".join(parts)


def _parse_percent(value: object) -> float | None:
    if value in (None, "", "N/A"):
        return None
    match = _NUMBER_PATTERN.search(str(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None

