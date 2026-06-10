from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

_BULLISH_TONE_LABELS = {
    "bull",
    "bullish",
    "positive",
    "긍정",
    "긍정적",
    "강세",
}
_BEARISH_TONE_LABELS = {
    "bear",
    "bearish",
    "negative",
    "부정",
    "부정적",
    "약세",
}
_NEUTRAL_TONE_LABELS = {
    "neutral",
    "mixed",
    "중립",
    "혼조",
}

_BULLISH_DIRECTION_LABELS = _BULLISH_TONE_LABELS | {"buy", "long"}
_BEARISH_DIRECTION_LABELS = _BEARISH_TONE_LABELS | {"sell", "short"}
_NEUTRAL_DIRECTION_LABELS = _NEUTRAL_TONE_LABELS | {"hold"}

_HARD_CATALYST_ENGLISH_TERMS = {
    "earnings",
    "guidance",
    "sec",
    "ir",
    "filing",
    "contract",
    "policy",
    "approval",
}
_HARD_CATALYST_KOREAN_TERMS = {
    "실적",
    "가이던스",
    "공시",
    "계약",
    "정책",
    "승인",
    "허가",
}


def build_news_evidence(
    row: Mapping[str, Any],
    *,
    signal_direction: object | None = None,
    llm_direction: object | None = None,
) -> dict[str, Any]:
    score = 35.0
    reason_chips: list[str] = []

    factors = _parse_json_object(row.get("factors_json"))
    confidence_meta = _parse_json_object(row.get("confidence_meta_json"))

    tone = normalize_news_tone(row.get("news_tone"))
    normalized_llm_direction = normalize_llm_direction(
        llm_direction if llm_direction is not None else row.get("llm_direction")
    )
    normalized_signal_direction = normalize_signal_direction(
        signal_direction if signal_direction is not None else row.get("signal_direction")
    )

    if tone == "bullish":
        score += 20
        reason_chips.append("positive_news")
    elif tone == "bearish":
        score -= 20
        reason_chips.append("negative_news")

    if normalized_llm_direction == "bull":
        score += 20
    elif normalized_llm_direction == "bear":
        score -= 20

    llm_alignment = _llm_alignment(normalized_signal_direction, normalized_llm_direction)
    if llm_alignment == "aligned" and normalized_signal_direction == "bull":
        score += 10
        reason_chips.append("llm_bull_aligned")
    elif llm_alignment == "conflict":
        reason_chips.append("llm_conflict")

    catalyst_tag = _as_text(row.get("catalyst_tag"))
    catalyst_recency_score = _first_number(
        row.get("catalyst_recency_score"),
        row.get("catalyst_recency"),
        factors.get("catalyst_recency_score"),
        factors.get("catalyst_recency"),
    )
    has_recent_catalyst = catalyst_recency_score > 0
    if has_recent_catalyst:
        score += 15
        reason_chips.append("recent_catalyst")

    has_hard_catalyst = _has_hard_catalyst(catalyst_tag)
    if has_hard_catalyst:
        score += 10
        reason_chips.append("hard_catalyst")

    source_count = _source_count(
        row.get("news_references"),
        row.get("key_news_source_titles"),
    )
    if source_count >= 2:
        score += 10
        reason_chips.append("source_coverage")
    elif source_count == 0:
        reason_chips.append("source_limited")

    search_evidence_score = _first_number(
        row.get("search_evidence_score"),
        confidence_meta.get("search_evidence_score"),
    )
    if search_evidence_score > 0:
        score += 5
        reason_chips.append("search_evidence")

    has_usable_news = any(
        [
            tone != "neutral",
            normalized_llm_direction in {"bull", "bear"},
            bool(catalyst_tag),
            has_recent_catalyst,
            has_hard_catalyst,
            source_count > 0,
            search_evidence_score > 0,
        ]
    )
    if not has_usable_news:
        score -= 10
        reason_chips.append("missing_news")

    score = round(max(0.0, min(100.0, score)), 10)
    strength = _strength(score, has_usable_news)

    return {
        "score": score,
        "strength": strength,
        "tone": tone,
        "llm_direction": normalized_llm_direction,
        "llm_alignment": llm_alignment,
        "catalyst_tag": catalyst_tag,
        "catalyst_recency_score": catalyst_recency_score,
        "source_count": source_count,
        "has_recent_catalyst": has_recent_catalyst,
        "has_hard_catalyst": has_hard_catalyst,
        "reason_chips": reason_chips,
        "summary": _summary(strength, tone, normalized_llm_direction, source_count),
    }


def normalize_news_tone(value: object) -> str:
    text = _normalize_text(_structured_label_value(value, ("label", "tone", "direction", "value")))
    if text in _BULLISH_TONE_LABELS:
        return "bullish"
    if text in _BEARISH_TONE_LABELS:
        return "bearish"
    if text in _NEUTRAL_TONE_LABELS:
        return "neutral"
    return "neutral"


def normalize_direction(value: object) -> str:
    text = _normalize_text(_structured_label_value(value, ("direction", "label", "tone", "value")))
    if text in _BULLISH_DIRECTION_LABELS:
        return "bull"
    if text in _BEARISH_DIRECTION_LABELS:
        return "bear"
    if text in _NEUTRAL_DIRECTION_LABELS:
        return "neutral"
    return "unknown"


def normalize_llm_direction(value: object) -> str:
    return normalize_direction(value)


def normalize_signal_direction(value: object) -> str:
    return normalize_direction(value)


def _llm_alignment(signal_direction: str, llm_direction: str) -> str:
    if llm_direction == "unknown" or signal_direction == "unknown":
        return "missing"
    if llm_direction in {"bull", "bear"} and signal_direction in {"bull", "bear"}:
        return "aligned" if llm_direction == signal_direction else "conflict"
    return "neutral"


def _parse_json_object(value: object) -> dict[str, Any]:
    parsed = _parse_json(value)
    return parsed if isinstance(parsed, dict) else {}


def _parse_json(value: object) -> Any:
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _source_count(*values: object) -> int:
    found_sequence = False
    for value in values:
        parsed = _parse_json(value)
        if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
            found_sequence = True
            if parsed:
                return len(parsed)
    if found_sequence:
        return 0
    return 0


def _first_number(*values: object) -> float:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            number = float(value)
            if math.isfinite(number):
                return number
            continue
        if isinstance(value, str) and value.strip():
            try:
                number = float(value)
            except ValueError:
                continue
            if math.isfinite(number):
                return number
    return 0.0


def _has_hard_catalyst(catalyst_tag: str) -> bool:
    normalized = catalyst_tag.lower()
    if any(term in normalized for term in _HARD_CATALYST_KOREAN_TERMS):
        return True
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized)
        for term in _HARD_CATALYST_ENGLISH_TERMS
    )


def _strength(score: float, has_usable_news: bool) -> str:
    if not has_usable_news:
        return "insufficient"
    if score >= 75:
        return "strong"
    if score >= 55:
        return "moderate"
    if score >= 35:
        return "weak"
    return "insufficient"


def _summary(strength: str, tone: str, llm_direction: str, source_count: int) -> str:
    return (
        f"{strength} news evidence with {tone} tone, "
        f"{llm_direction} LLM direction, and {source_count} sources."
    )


def _normalize_text(value: object) -> str:
    return _as_text(value).lower()


def _structured_label_value(value: object, keys: tuple[str, ...]) -> object:
    if isinstance(value, Mapping):
        for key in keys:
            candidate = value.get(key)
            if candidate is not None and _as_text(candidate):
                return candidate
    return value


def _as_text(value: object) -> str:
    return str(value or "").strip()
