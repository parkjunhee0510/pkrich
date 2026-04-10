"""Analyze earnings surprise history patterns from quarterly financials."""
from __future__ import annotations

import re
from typing import Any

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def build_earnings_surprise_summary(
    quarterly_financials: list[dict[str, str]],
) -> dict[str, Any]:
    """Analyze beat/miss patterns from quarterly financial data.

    Returns a dict with:
    - consecutive_beats: number of consecutive beats from most recent quarter
    - consecutive_misses: number of consecutive misses from most recent quarter
    - beat_rate: percentage of quarters that beat estimates (out of those with data)
    - avg_surprise_pct: average surprise percentage
    - pattern: "consistent_beat", "consistent_miss", "volatile", or "insufficient_data"
    - post_earnings_hint: text hint about likely reaction based on pattern
    - quarters_analyzed: how many quarters had usable data
    """
    records = _extract_beat_miss_records(quarterly_financials)
    if len(records) < 2:
        return {
            "consecutive_beats": 0,
            "consecutive_misses": 0,
            "beat_rate": "N/A",
            "avg_surprise_pct": "N/A",
            "pattern": "insufficient_data",
            "post_earnings_hint": "실적 서프라이즈 데이터 부족으로 패턴 판단 불가",
            "quarters_analyzed": len(records),
        }

    beats = sum(1 for r in records if r["result"] == "beat")
    misses = sum(1 for r in records if r["result"] == "miss")
    total = len(records)
    beat_rate = (beats / total) * 100 if total > 0 else 0

    surprises = [r["surprise_pct"] for r in records if r["surprise_pct"] is not None]
    avg_surprise = sum(surprises) / len(surprises) if surprises else None

    # Consecutive streaks from most recent
    consecutive_beats = 0
    consecutive_misses = 0
    for record in records:
        if record["result"] == "beat":
            if consecutive_misses == 0:
                consecutive_beats += 1
            else:
                break
        elif record["result"] == "miss":
            if consecutive_beats == 0:
                consecutive_misses += 1
            else:
                break
        else:
            break

    # Classify pattern
    if beat_rate >= 75 and consecutive_beats >= 3:
        pattern = "consistent_beat"
        hint = f"최근 {consecutive_beats}분기 연속 실적 beat — 시장 기대치가 이미 높을 수 있음, beat 폭이 중요"
    elif beat_rate <= 25 and consecutive_misses >= 2:
        pattern = "consistent_miss"
        hint = f"최근 {consecutive_misses}분기 연속 miss — 가이던스 하향 또는 구조적 문제 점검 필요"
    elif beat_rate >= 50:
        pattern = "mostly_beat"
        hint = f"최근 {total}분기 중 {beats}분기 beat ({beat_rate:.0f}%) — 실적 발표 전후 긍정적 반응 가능성"
    else:
        pattern = "volatile"
        hint = f"Beat/miss가 불규칙 (beat {beats}/{total}) — 실적 발표 시 변동성 확대 주의"

    return {
        "consecutive_beats": consecutive_beats,
        "consecutive_misses": consecutive_misses,
        "beat_rate": f"{beat_rate:.0f}%",
        "avg_surprise_pct": f"{avg_surprise:+.1f}%" if avg_surprise is not None else "N/A",
        "pattern": pattern,
        "post_earnings_hint": hint,
        "quarters_analyzed": total,
    }


def _extract_beat_miss_records(
    quarterly_financials: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Extract beat/miss records from quarterly financials, most recent first."""
    records: list[dict[str, Any]] = []
    for quarter in quarterly_financials:
        beat_miss = str(quarter.get("beat_miss", "")).strip().lower()
        surprise_str = str(quarter.get("surprise_pct", "N/A")).strip()

        if beat_miss not in ("beat", "miss", "meet"):
            continue

        surprise_val = _parse_float(surprise_str)
        records.append({
            "quarter": quarter.get("quarter", ""),
            "result": beat_miss,
            "surprise_pct": surprise_val,
            "estimated_eps": quarter.get("estimated_eps", "N/A"),
            "actual_eps": quarter.get("actual_eps", quarter.get("eps", "N/A")),
        })

    return records


def _parse_float(text: str) -> float | None:
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
