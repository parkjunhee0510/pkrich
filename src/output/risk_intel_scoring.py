"""Pure scoring helpers for risk intelligence graph artifacts."""

from __future__ import annotations

from math import prod
from typing import Iterable

from src.output.risk_intel_config import CAP_VALUES, CONFIDENCE_BANDS, SCORE_WEIGHTS, TRUST_TIER_SCORES


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def raw_score(score_breakdown: dict[str, float]) -> float:
    total = 0.0
    for key, weight in SCORE_WEIGHTS.items():
        total += weight * clamp01(float(score_breakdown.get(key, 0.0) or 0.0))
    return round(total, 4)


def apply_caps(raw: float, caps_applied: list[str]) -> dict[str, object]:
    rounded_raw = round(float(raw), 4)
    known_caps = [CAP_VALUES[name] for name in caps_applied if name in CAP_VALUES]
    if not known_caps:
        return {"raw_score": rounded_raw, "score": rounded_raw, "score_kind": "final", "cap_value": None}

    cap_value = min(known_caps)
    return {
        "raw_score": rounded_raw,
        "score": round(min(rounded_raw, cap_value), 4),
        "score_kind": "capped_final",
        "cap_value": cap_value,
    }


def alert_level_for_score(score: float) -> str:
    if score >= 0.70:
        return "alert"
    if score >= 0.40:
        return "warning"
    return "observation"


def evidence_strength(source_records: Iterable[dict[str, object]]) -> float:
    records = list(source_records)
    if not records:
        return 0.0

    strongest = max(
        TRUST_TIER_SCORES.get(str(record.get("trust_tier", "unknown")), 0.20)
        for record in records
    )
    independent_non_social_types = {
        str(record.get("source_type", "unknown"))
        for record in records
        if str(record.get("trust_tier", "unknown")) != "social"
    }
    bonus = max(0, len(independent_non_social_types) - 1) * 0.05
    return round(clamp01(strongest + bonus), 4)


def confidence_for_edge(evidence_type: str, band_key: str) -> float:
    low, high = CONFIDENCE_BANDS[evidence_type][band_key]
    return round((low + high) / 2.0, 4)


def geometric_mean(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values if float(value) >= 0.0]
    if not numbers:
        return 0.0
    return round(prod(numbers) ** (1.0 / len(numbers)), 4)


def freshness_score(*, age_hours: float, half_life_hours: float) -> float:
    if half_life_hours <= 0:
        return 0.0
    return round(clamp01(0.5 ** (float(age_hours) / float(half_life_hours))), 4)
