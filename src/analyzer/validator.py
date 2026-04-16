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
            news_tone = sanitized.get("news_tone") or intermediate.get("news_tone") or fallback.get("news_tone") or {}
            if _has_tone_signal_conflict(news_tone, sanitized.get("signal_or_takeaway", "")):
                warnings.append(
                    ValidationWarning(
                        "consistency_warning",
                        "signal_or_takeaway",
                        "signal direction conflicts with news tone",
                    )
                )
                if "signal_or_takeaway" in fallback:
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
