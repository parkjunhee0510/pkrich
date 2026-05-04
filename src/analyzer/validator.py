from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.analyzer.signal_levels import allowed_signal_levels


_PRICE_TOKEN = re.compile(r"(?:\$|USD\s*)(\d[\d,]*\.?\d*)|(\d[\d,]*\.?\d*)\s*USD", re.IGNORECASE)
_PERCENT_TOKEN = re.compile(r"([-+]?\d[\d,]*\.?\d*)%")
_NUMBER_TOKEN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_ASCII_LETTER = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class ValidationWarning:
    category: str
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    sanitized_response: dict[str, Any]
    warnings: list[ValidationWarning] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.warnings

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for warning in self.warnings:
            counts[warning.category] = counts.get(warning.category, 0) + 1
        return counts


@dataclass(frozen=True)
class NumericMismatch:
    grade: str
    value_type: str
    number: float
    nearest_known: float | None
    deviation: float | None


class ResponseValidator:
    def validate(
        self,
        response: dict[str, Any],
        schema: dict[str, Any],
        ticker_data: dict[str, Any],
    ) -> ValidationResult:
        sanitized = dict(response)
        warnings: list[ValidationWarning] = []
        fallback = dict(ticker_data.get("fallback", {}))
        raw_payload = dict(ticker_data.get("raw_payload", {}))
        intermediate = dict(ticker_data.get("intermediate", {}))

        for field_name in schema.keys():
            if field_name not in sanitized:
                warnings.append(ValidationWarning("schema_violation", field_name, f"{field_name} missing"))
                if field_name in fallback:
                    sanitized[field_name] = fallback[field_name]
                continue
            if not _matches_expected_type(sanitized[field_name], schema[field_name]):
                warnings.append(ValidationWarning("schema_violation", field_name, f"{field_name} type mismatch"))
                if field_name in fallback:
                    sanitized[field_name] = fallback[field_name]

        if "key_news" in sanitized:
            hallucinated = _find_hallucinated_key_news(sanitized.get("key_news", []), raw_payload.get("news", []))
            for item in hallucinated:
                warnings.append(ValidationWarning("hallucination_warning", "key_news", f"unmatched title-like key_news: {item}"))
            if hallucinated and "key_news" in fallback:
                sanitized["key_news"] = fallback["key_news"]

        for field_name in sorted(sanitized.keys()):
            if field_name == "signal_or_takeaway":
                continue
            mismatch = _find_fact_mismatch(sanitized.get(field_name), raw_payload, intermediate)
            if mismatch is None:
                continue
            message = _format_numeric_mismatch_message(field_name, mismatch)
            if mismatch.grade == "minor":
                warnings.append(ValidationWarning("fact_warning", field_name, message))
                continue
            if mismatch.grade == "suspect":
                warnings.append(ValidationWarning("fact_warning", field_name, message))
                if field_name in fallback:
                    sanitized[field_name] = fallback[field_name]
                continue
            if mismatch.grade == "hallucination":
                warnings.append(ValidationWarning("hallucination_warning", field_name, message))
                if field_name in fallback:
                    sanitized[field_name] = fallback[field_name]

        if "signal_or_takeaway" in sanitized:
            signal_text = str(sanitized.get("signal_or_takeaway", ""))
            news_tone = sanitized.get("news_tone") or intermediate.get("news_tone") or fallback.get("news_tone") or {}
            signal_replaced = False
            if _has_tone_signal_conflict(news_tone, signal_text):
                warnings.append(
                    ValidationWarning(
                        "consistency_warning",
                        "signal_or_takeaway",
                        "signal direction conflicts with news tone",
                    )
                )
                if "signal_or_takeaway" in fallback:
                    sanitized["signal_or_takeaway"] = fallback["signal_or_takeaway"]
                    signal_replaced = True
            if not signal_replaced:
                current_price = _extract_current_price(raw_payload, intermediate)
                allowed_levels = allowed_signal_levels(
                    raw_payload,
                    intermediate.get("trade_frame", {}),
                    _signal_direction(signal_text),
                )
                price_issues = _find_signal_price_issues(
                    signal_text,
                    current_price=current_price,
                    allowed_targets=allowed_levels.get("targets", []),
                    allowed_stop=allowed_levels.get("stop", []),
                )
                price_issues.extend(
                    _find_signal_whitelist_issues(
                        signal_text,
                        raw_payload=raw_payload,
                        intermediate=intermediate,
                        allowed=allowed_levels,
                    )
                )
                for issue in price_issues:
                    warnings.append(ValidationWarning("fact_warning", "signal_or_takeaway", issue))
                if price_issues and "signal_or_takeaway" in fallback:
                    sanitized["signal_or_takeaway"] = fallback["signal_or_takeaway"]

        return ValidationResult(sanitized_response=sanitized, warnings=warnings)


def _matches_expected_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str) and bool(value.strip())
    if expected_type == "list":
        return isinstance(value, list)
    if expected_type == "dict":
        return isinstance(value, dict)
    return True


def _find_hallucinated_key_news(key_news: list[Any], news_items: list[Any]) -> list[str]:
    headlines = [
        _normalize_text(str(item.get("title", "")))
        for item in news_items
        if isinstance(item, dict) and str(item.get("title", "")).strip()
    ]
    if not headlines:
        return []
    warnings: list[str] = []
    for item in key_news:
        text = str(item).strip()
        if not _looks_like_title(text):
            continue
        normalized = _normalize_text(text)
        if normalized and all(_headline_similarity(normalized, headline) < 0.6 for headline in headlines):
            warnings.append(text)
    return warnings


def _find_fact_mismatch(value: Any, raw_payload: dict[str, Any], intermediate: dict[str, Any]) -> NumericMismatch | None:
    text_values = _collect_text_values(value)
    if not text_values:
        return None
    known_prices, known_percents = _extract_known_numeric_values(raw_payload, intermediate)
    worst: NumericMismatch | None = None
    for text in text_values:
        for number in _extract_price_numbers(text):
            mismatch = _build_numeric_mismatch("price", number, known_prices)
            worst = _pick_worse_mismatch(worst, mismatch)
        for number in _extract_percent_numbers(text):
            mismatch = _build_numeric_mismatch("percent", number, known_percents)
            worst = _pick_worse_mismatch(worst, mismatch)
    return worst


def _has_tone_signal_conflict(news_tone: Any, signal: str) -> bool:
    label = ""
    if isinstance(news_tone, dict):
        label = str(news_tone.get("label", "")).strip().lower()
    signal_text = str(signal).strip()
    if not label or not signal_text:
        return False
    positive = any(token in signal_text for token in ("매수", "상승", "bull"))
    negative = any(token in signal_text for token in ("매도", "하락", "bear"))
    if label == "bullish" and negative:
        return True
    if label == "bearish" and positive:
        return True
    return False


def _collect_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        return [str(item) for item in value.values() if isinstance(item, str)]
    return []


def _extract_known_numeric_values(raw_payload: dict[str, Any], intermediate: dict[str, Any]) -> tuple[list[float], list[float]]:
    known_prices: list[float] = []
    known_percents: list[float] = []
    for source in (raw_payload, intermediate):
        for text in _walk_strings(source):
            known_prices.extend(_extract_price_numbers(text))
            known_percents.extend(_extract_percent_numbers(text))
    return known_prices, known_percents


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_walk_strings(item))
        return strings
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_walk_strings(item))
        return strings
    return []


def _extract_price_numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in _PRICE_TOKEN.findall(text or ""):
        candidate = next((part for part in match if part), "")
        number = _to_float(candidate)
        if number is not None:
            values.append(number)
    return values


def _extract_percent_numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in _PERCENT_TOKEN.findall(text or ""):
        number = _to_float(match)
        if number is not None:
            values.append(number)
    return values


def _build_numeric_mismatch(value_type: str, target: float, known_values: list[float]) -> NumericMismatch | None:
    grade, nearest_known, deviation = _grade_mismatch(target, known_values)
    if grade in (None, "rounding"):
        return None
    return NumericMismatch(
        grade=grade,
        value_type=value_type,
        number=target,
        nearest_known=nearest_known,
        deviation=deviation,
    )


def _grade_mismatch(target: float, known_values: list[float]) -> tuple[str | None, float | None, float | None]:
    if not known_values:
        return None, None, None
    nearest_known: float | None = None
    min_dev: float | None = None
    for known in known_values:
        baseline = abs(known) if known != 0 else 1.0
        deviation = abs(target - known) / baseline
        if min_dev is None or deviation < min_dev:
            min_dev = deviation
            nearest_known = known
    if min_dev is None:
        return None, None, None
    if min_dev < 0.005:
        return "rounding", nearest_known, min_dev
    if min_dev < 0.02:
        return "minor", nearest_known, min_dev
    if min_dev < 0.05:
        return "suspect", nearest_known, min_dev
    return "hallucination", nearest_known, min_dev


def _pick_worse_mismatch(current: NumericMismatch | None, candidate: NumericMismatch | None) -> NumericMismatch | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    severity_rank = {"minor": 1, "suspect": 2, "hallucination": 3}
    current_rank = severity_rank.get(current.grade, 0)
    candidate_rank = severity_rank.get(candidate.grade, 0)
    if candidate_rank != current_rank:
        return candidate if candidate_rank > current_rank else current
    current_dev = current.deviation or 0.0
    candidate_dev = candidate.deviation or 0.0
    return candidate if candidate_dev > current_dev else current


def _format_numeric_mismatch_message(field_name: str, mismatch: NumericMismatch) -> str:
    if mismatch.nearest_known is None or mismatch.deviation is None:
        return f"{field_name} contains unsupported numeric values"
    deviation_pct = mismatch.deviation * 100
    return (
        f"{field_name} contains {mismatch.grade} {mismatch.value_type} mismatch: "
        f"{mismatch.number} vs known {mismatch.nearest_known} ({deviation_pct:.2f}% dev)"
    )


def _looks_like_title(text: str) -> bool:
    if len(text) < 20:
        return False
    ascii_chars = len(_ASCII_LETTER.findall(text))
    return ascii_chars >= max(8, len(text) // 3)


def _headline_similarity(left: str, right: str) -> float:
    left_tokens = set(_normalize_text(left).split())
    right_tokens = set(_normalize_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    return intersection / max(len(left_tokens), len(right_tokens))


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


_TARGET_SEGMENT_RE = re.compile(r"목표[^|]*?([\d.,]+)\s*/\s*([\d.,]+)")
_TARGET_SEGMENT_TEXT_RE = re.compile(r"목표(?P<segment>[^|]*)")
_STOP_SEGMENT_RE = re.compile(r"손절(?P<segment>[^|]*)")
_LONG_TOKENS = ("매수 관찰", "매수 유지", "매수 우선")
_SHORT_TOKENS = ("매도 경계", "매도 관찰", "매도 유지", "매도")


def _find_signal_price_issues(
    signal_text: str,
    *,
    current_price: float | None = None,
    allowed_targets: list[float] | None = None,
    allowed_stop: list[float] | None = None,
) -> list[str]:
    """Detect internal price-logic errors in a signal string.

    The module prompt enforces the shape
    ``[방향] — [catalyst] | 진입 트리거 … | 목표 A/B | 손절 C``. Even when the
    shape is honored, LLMs occasionally emit non-monotone target pairs or a
    stop loss on the wrong side of the first target. Those are factually
    inconsistent regardless of current price, so flag them as fact warnings
    so the orchestrator can fall back to the heuristic takeaway.
    """
    text = str(signal_text or "")
    if not text.strip():
        return []
    direction = _signal_direction(text)
    if direction is None:
        return []
    issues: list[str] = []
    targets = _extract_targets(text)
    stop = _extract_stop(text)
    if "목표" in text and targets is None and not _target_segment_allows_missing(text):
        issues.append("targets must use slash-delimited pair")
    if targets:
        t1, t2 = targets
        if direction == "long" and t2 <= t1:
            issues.append(f"targets not ascending for long: {t1}/{t2}")
        elif direction == "short" and t2 >= t1:
            issues.append(f"targets not descending for short: {t1}/{t2}")
    if stop is not None and targets:
        t1 = targets[0]
        if direction == "long" and stop >= t1:
            issues.append(f"stop {stop} not below first target {t1} for long")
        elif direction == "short" and stop <= t1:
            issues.append(f"stop {stop} not above first target {t1} for short")
    if current_price is not None and current_price > 0:
        allowed_target_values = allowed_targets or []
        allowed_stop_values = allowed_stop or []
        if (
            stop is not None
            and abs(stop - current_price) / current_price > 0.15
            and not _is_allowed_level(stop, allowed_stop_values)
        ):
            issues.append(f"stop {stop} outside 15% band from current price {current_price}")
        if targets:
            for target in targets:
                if (
                    abs(target - current_price) / current_price > 0.30
                    and not _is_allowed_level(target, allowed_target_values)
                ):
                    issues.append(f"target {target} outside 30% band from current price {current_price}")
    return issues


def _find_signal_whitelist_issues(
    signal_text: str,
    *,
    raw_payload: dict[str, Any],
    intermediate: dict[str, Any],
    allowed: dict[str, list[float]] | None = None,
) -> list[str]:
    text = str(signal_text or "")
    if not text.strip():
        return []
    direction = _signal_direction(text)
    targets = _extract_targets(text)
    stop = _extract_stop(text)
    if targets is None and stop is None:
        return []
    allowed = allowed or allowed_signal_levels(raw_payload, intermediate.get("trade_frame", {}), direction)
    issues: list[str] = []
    allowed_targets = allowed.get("targets", [])
    allowed_stop = allowed.get("stop", [])
    if targets:
        for target in targets:
            grade, nearest, _ = _grade_mismatch(target, allowed_targets)
            if grade not in (None, "rounding"):
                issues.append(
                    f"target {target} not in MUST_USE_VALUES whitelist"
                    + (f" (nearest {nearest})" if nearest is not None else "")
                )
    if stop is not None:
        grade, nearest, _ = _grade_mismatch(stop, allowed_stop)
        if grade not in (None, "rounding"):
            issues.append(
                f"stop {stop} not in MUST_USE_VALUES whitelist"
                + (f" (nearest {nearest})" if nearest is not None else "")
            )
    return issues


def _target_segment_allows_missing(text: str) -> bool:
    match = _TARGET_SEGMENT_TEXT_RE.search(text)
    if not match:
        return False
    compact = match.group("segment").strip().upper().replace(" ", "").replace("N/A", "NA")
    if not compact:
        return False
    return all(part in {"N/A", "NA", "—", "-"} for part in compact.split("/"))


def _is_allowed_level(value: float, allowed_values: list[float]) -> bool:
    for allowed in allowed_values:
        baseline = abs(allowed) if allowed != 0 else 1.0
        if abs(value - allowed) / baseline < 0.005:
            return True
    return False


def _signal_direction(text: str) -> str | None:
    for token in _SHORT_TOKENS:
        if token in text:
            return "short"
    for token in _LONG_TOKENS:
        if token in text:
            return "long"
    return None


def _extract_targets(text: str) -> tuple[float, float] | None:
    match = _TARGET_SEGMENT_RE.search(text)
    if not match:
        return None
    first = _to_float(match.group(1))
    second = _to_float(match.group(2))
    if first is None or second is None:
        return None
    return first, second


def _extract_stop(text: str) -> float | None:
    match = _STOP_SEGMENT_RE.search(text)
    if not match:
        return None
    values = [
        value
        for value in (_to_float(raw.group(0)) for raw in _NUMBER_TOKEN.finditer(match.group("segment")))
        if value is not None
    ]
    if not values:
        return None
    return values[-1]


def _to_float(raw: str) -> float | None:
    try:
        normalized = str(raw).replace(",", "").strip()
        if not normalized:
            return None
        number = float(_NUMBER_TOKEN.search(normalized).group(0))  # type: ignore[union-attr]
        if number.is_integer() and 1900 <= number <= 2100:
            return None
        return number
    except (AttributeError, TypeError, ValueError):
        return None


def _extract_current_price(raw_payload: dict[str, Any], intermediate: dict[str, Any]) -> float | None:
    direct_price = raw_payload.get("price")
    if isinstance(direct_price, (int, float)):
        return float(direct_price)
    parsed_direct = _to_float(str(direct_price or ""))
    if parsed_direct is not None:
        return parsed_direct
    price_action = intermediate.get("price_action")
    if isinstance(price_action, dict):
        for key in ("current_price", "price"):
            parsed_price = _to_float(str(price_action.get(key, "")))
            if parsed_price is not None:
                return parsed_price
    data_snapshot = intermediate.get("data_snapshot")
    if isinstance(data_snapshot, dict):
        parsed_snapshot = _to_float(str(data_snapshot.get("Price", "")))
        if parsed_snapshot is not None:
            return parsed_snapshot
    return None
