from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


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

        fact_warning_fields = {
            field_name
            for field_name, value in sanitized.items()
            if _has_fact_mismatch(value, raw_payload, intermediate)
        }
        for field_name in sorted(fact_warning_fields):
            warnings.append(ValidationWarning("fact_warning", field_name, f"{field_name} contains unsupported numeric values"))
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
                price_issues = _find_signal_price_issues(signal_text, current_price=current_price)
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


def _has_fact_mismatch(value: Any, raw_payload: dict[str, Any], intermediate: dict[str, Any]) -> bool:
    text_values = _collect_text_values(value)
    if not text_values:
        return False
    known_prices, known_percents = _extract_known_numeric_values(raw_payload, intermediate)
    for text in text_values:
        for number in _extract_price_numbers(text):
            if not _matches_known_value(number, known_prices):
                return True
        for number in _extract_percent_numbers(text):
            if not _matches_known_value(number, known_percents):
                return True
    return False


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


def _matches_known_value(target: float, known_values: list[float]) -> bool:
    for known in known_values:
        baseline = abs(known) if known != 0 else 1.0
        if abs(target - known) / baseline <= 0.05:
            return True
    return False


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
_STOP_SEGMENT_RE = re.compile(r"손절[^|]*?([\d.,]+)")
_LONG_TOKENS = ("매수 관찰", "매수 유지", "매수 우선")
_SHORT_TOKENS = ("매도 경계", "매도 관찰", "매도 유지", "매도")


def _find_signal_price_issues(signal_text: str, *, current_price: float | None = None) -> list[str]:
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
    if "목표" in text and targets is None:
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
        if stop is not None and abs(stop - current_price) / current_price > 0.15:
            issues.append(f"stop {stop} outside 15% band from current price {current_price}")
        if targets:
            for target in targets:
                if abs(target - current_price) / current_price > 0.30:
                    issues.append(f"target {target} outside 30% band from current price {current_price}")
    return issues


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
    return _to_float(match.group(1))


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
