from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_PRICE_TOKEN = re.compile(r"(?:\$|USD\s*)(\d[\d,]*\.?\d*)|(\d[\d,]*\.?\d*)\s*USD", re.IGNORECASE)
_PERCENT_TOKEN = re.compile(r"([-+]?\d[\d,]*\.?\d*)%")
_NUMBER_TOKEN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_ASCII_LETTER = re.compile(r"[A-Za-z]")
_HANGUL = re.compile(r"[가-힣]")
# URL citation matcher — any http(s)://host/path token. The LLM sometimes
# inlines URLs in summary/signals text as "evidence"; a URL not present in
# `raw_payload.news[*].link` is fabricated.
_URL_TOKEN = re.compile(r"https?://[^\s)\"'<>]+", re.IGNORECASE)

# Numeric matching tolerances. Looser tolerances let invented numbers slip
# past via "close enough" collisions with unrelated values in the payload.
_PRICE_RELATIVE_TOL = 0.03  # 3% — was 5%
_PERCENT_RELATIVE_TOL = 0.10  # 10% — only matters for very large percents
_PERCENT_ABSOLUTE_FLOOR_PP = 0.3  # a LLM "5%" cannot match a real "4.5%" via relative math alone

# Headline similarity: token fraction PLUS minimum shared token count, so
# short generic overlaps ("Apple Q3 results") don't trivially match.
_HEADLINE_JACCARD_MIN = 0.6
_HEADLINE_SHARED_TOKENS_MIN = 3


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
            if hallucinated:
                if "key_news" in fallback:
                    sanitized["key_news"] = fallback["key_news"]
                else:
                    # No fallback — drop the tainted items rather than let the
                    # caller persist a fabricated headline into the decision board.
                    kept = [
                        item for item in sanitized.get("key_news", [])
                        if str(item).strip() not in hallucinated
                    ]
                    sanitized["key_news"] = kept
                    warnings.append(
                        ValidationWarning(
                            "dropped_unsupported",
                            "key_news",
                            f"dropped {len(hallucinated)} hallucinated headline(s) (no fallback)",
                        )
                    )

        known_urls = _collect_known_urls(raw_payload, intermediate)
        url_mismatch_fields: list[tuple[str, list[str]]] = []
        for field_name, value in sanitized.items():
            unknown = _find_unknown_urls(value, known_urls)
            if unknown:
                url_mismatch_fields.append((field_name, unknown))
        for field_name, urls in url_mismatch_fields:
            warnings.append(
                ValidationWarning(
                    "hallucination_warning",
                    field_name,
                    f"{field_name} cites URL(s) not in collected news: {urls[:3]}",
                )
            )
            if field_name in fallback:
                sanitized[field_name] = fallback[field_name]
            else:
                sanitized[field_name] = _strip_unknown_urls(sanitized[field_name], known_urls)
                warnings.append(
                    ValidationWarning(
                        "dropped_unsupported",
                        field_name,
                        f"{field_name} had fabricated URL(s) stripped (no fallback)",
                    )
                )

        fact_warning_fields = {
            field_name
            for field_name, value in sanitized.items()
            if _should_flag_fact_mismatch(field_name, value, raw_payload, intermediate, fallback)
        }
        for field_name in sorted(fact_warning_fields):
            warnings.append(ValidationWarning("fact_warning", field_name, f"{field_name} contains unsupported numeric values"))
            if field_name in fallback:
                sanitized[field_name] = fallback[field_name]
            else:
                # No fallback — drop to a safe empty shape. Keeping the
                # tainted value would silently propagate fabricated numbers
                # into the decision board (observed failure mode).
                sanitized[field_name] = _empty_like(sanitized[field_name])
                warnings.append(
                    ValidationWarning(
                        "dropped_unsupported",
                        field_name,
                        f"{field_name} dropped (no fallback for unsupported numbers)",
                    )
                )

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

        signal_validation_messages = validate_signal_takeaway(
            sanitized.get("signal_or_takeaway", ""),
            _coerce_price_value(raw_payload.get("price")),
            sanitized.get("trade_frame", {}),
        )
        if signal_validation_messages:
            for message in signal_validation_messages:
                warnings.append(
                    ValidationWarning(
                        "signal_validation_warning",
                        "signal_or_takeaway",
                        message,
                    )
                )
            if "signal_or_takeaway" in fallback:
                sanitized["signal_or_takeaway"] = fallback["signal_or_takeaway"]
            else:
                sanitized["signal_or_takeaway"] = ""
            if "trade_frame" in fallback:
                sanitized["trade_frame"] = fallback["trade_frame"]
            elif isinstance(sanitized.get("trade_frame"), dict):
                sanitized["trade_frame"] = _empty_trade_frame_like(sanitized["trade_frame"])

        return ValidationResult(sanitized_response=sanitized, warnings=warnings)


def validate_signal_takeaway(
    signal: Any,
    price: float | None,
    trade_frame: Any,
) -> list[str]:
    if price is None or price <= 0:
        return []

    signal_text = str(signal or "").strip()
    if not signal_text:
        return []

    trade_frame_dict = trade_frame if isinstance(trade_frame, dict) else {}
    messages: list[str] = []
    direction = _infer_signal_direction(signal_text)

    target_values = _extract_trade_frame_targets(signal_text, trade_frame_dict)
    for target in target_values:
        if target < (price * 0.5) or target > (price * 3.0):
            messages.append(
                f"target price {target:.2f} is outside realistic range for current price {price:.2f}"
            )
            break

    stop_value = _extract_stop_value(signal_text, trade_frame_dict)
    if direction == "long" and stop_value is not None and stop_value >= price:
        messages.append(
            f"long signal stop loss {stop_value:.2f} must be below current price {price:.2f}"
        )

    if direction == "long":
        target_value = target_values[0] if target_values else None
        if target_value is not None and target_value <= price:
            messages.append(
                f"long signal target {target_value:.2f} must be above current price {price:.2f}"
            )

    return messages


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
        if _contains_hangul(text):
            # key_news is intentionally written as short Korean summaries, not
            # verbatim English headlines. Headline-similarity checks create
            # false positives here, so keep Korean summaries out of the
            # title-matching path and let URL/numeric validation cover the rest.
            continue
        if not _looks_like_title(text):
            continue
        normalized = _normalize_text(text)
        if normalized and all(
            _headline_similarity(normalized, headline) < _HEADLINE_JACCARD_MIN
            for headline in headlines
        ):
            warnings.append(text)
    return warnings


def _has_fact_mismatch(
    value: Any,
    raw_payload: dict[str, Any],
    intermediate: dict[str, Any],
    fallback: dict[str, Any],
) -> bool:
    text_values = _collect_text_values(value)
    if not text_values:
        return False
    known_prices, known_percents = _extract_known_numeric_values(raw_payload, intermediate, fallback)
    for text in text_values:
        for number in _extract_price_numbers(text):
            if not _matches_known_value(number, known_prices, _PRICE_RELATIVE_TOL):
                return True
        for number in _extract_percent_numbers(text):
            if not _matches_known_percent(number, known_percents):
                return True
    return False


def _collect_known_urls(raw_payload: dict[str, Any], intermediate: dict[str, Any]) -> set[str]:
    """All http(s) URLs anywhere in collected data — news links, filings, IR."""
    known: set[str] = set()
    for source in (raw_payload, intermediate):
        for text in _walk_strings(source):
            for url in _URL_TOKEN.findall(text or ""):
                known.add(_normalize_url(url))
    return known


def _normalize_url(url: str) -> str:
    # Drop trailing punctuation/whitespace — markdown or prose frequently
    # appends '.' or ',' after the URL.
    return url.rstrip(" \t\n\r.,;:)]").lower()


def _find_unknown_urls(value: Any, known_urls: set[str]) -> list[str]:
    unknown: list[str] = []
    for text in _walk_strings(value):
        for raw_url in _URL_TOKEN.findall(text or ""):
            norm = _normalize_url(raw_url)
            if norm not in known_urls:
                unknown.append(raw_url)
    return unknown


def _strip_unknown_urls(value: Any, known_urls: set[str]) -> Any:
    if isinstance(value, str):
        return _strip_urls_from_text(value, known_urls)
    if isinstance(value, list):
        return [_strip_unknown_urls(item, known_urls) for item in value]
    if isinstance(value, dict):
        return {k: _strip_unknown_urls(v, known_urls) for k, v in value.items()}
    return value


def _strip_urls_from_text(text: str, known_urls: set[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        norm = _normalize_url(match.group(0))
        return match.group(0) if norm in known_urls else ""
    cleaned = _URL_TOKEN.sub(_replace, text)
    # Collapse double spaces that result from stripping inline URLs.
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _empty_like(value: Any) -> Any:
    if isinstance(value, str):
        return ""
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    return value


def _empty_trade_frame_like(value: dict[str, Any]) -> dict[str, str]:
    return {str(key): "" for key in value.keys()}


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


def _should_flag_fact_mismatch(
    field_name: str,
    value: Any,
    raw_payload: dict[str, Any],
    intermediate: dict[str, Any],
    fallback: dict[str, Any],
) -> bool:
    if field_name == "financial_highlights" and isinstance(value, list):
        text_values = [str(item) for item in value if isinstance(item, str) and str(item).strip()]
        if not text_values:
            return False
        mismatches = [
            text
            for text in text_values
            if _has_fact_mismatch(text, raw_payload, intermediate, fallback)
        ]
        # Highlights frequently mix a few hard numbers with short qualitative
        # context. Warn only when the whole field looks unsupported, not when a
        # single line uses a looser summary phrase.
        return len(mismatches) == len(text_values)
    return _has_fact_mismatch(value, raw_payload, intermediate, fallback)


def _coerce_price_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if numeric > 0 else None
    if isinstance(value, str):
        return _to_float(value)
    return None


def _infer_signal_direction(signal_text: str) -> str:
    normalized = signal_text.strip().lower()
    positive_tokens = ("매수", "bull", "상승", "강세", "롱", "buy")
    negative_tokens = ("매도", "bear", "하락", "약세", "숏", "sell")
    if any(token in normalized for token in positive_tokens):
        return "long"
    if any(token in normalized for token in negative_tokens):
        return "short"
    return "neutral"


def _extract_trade_frame_targets(signal_text: str, trade_frame: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for key in ("target_1", "target_2"):
        raw = trade_frame.get(key)
        numeric = _extract_first_price(raw)
        if numeric is not None:
            values.append(numeric)

    for match in re.finditer(r"(?:목표가|목표|target)\s*[:\-]?\s*(?:\$|USD\s*)?(\d[\d,]*\.?\d*)", signal_text, re.IGNORECASE):
        numeric = _to_float(match.group(1))
        if numeric is not None:
            values.append(numeric)
    return values


def _extract_stop_value(signal_text: str, trade_frame: dict[str, Any]) -> float | None:
    stop_numeric = _extract_first_price(trade_frame.get("stop_loss"))
    if stop_numeric is not None:
        return stop_numeric

    match = re.search(r"(?:손절|stop)\s*[:\-]?\s*(?:\$|USD\s*)?(\d[\d,]*\.?\d*)", signal_text, re.IGNORECASE)
    if not match:
        return None
    return _to_float(match.group(1))


def _extract_first_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if numeric > 0 else None

    text = str(value)
    for number in _extract_price_numbers(text):
        if number > 0:
            return number
    return None


def _collect_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        return [str(item) for item in value.values() if isinstance(item, str)]
    return []


def _extract_known_numeric_values(
    raw_payload: dict[str, Any],
    intermediate: dict[str, Any],
    fallback: dict[str, Any],
) -> tuple[list[float], list[float]]:
    known_prices: list[float] = []
    known_percents: list[float] = []
    for source in (raw_payload, intermediate, fallback):
        for text in _walk_strings(source):
            known_prices.extend(_extract_price_numbers(text))
            known_percents.extend(_extract_percent_numbers(text))
    return known_prices, known_percents


def _contains_hangul(text: str) -> bool:
    return bool(_HANGUL.search(text))


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


def _matches_known_value(target: float, known_values: list[float], relative_tol: float = 0.05) -> bool:
    for known in known_values:
        baseline = abs(known) if known != 0 else 1.0
        if abs(target - known) / baseline <= relative_tol:
            return True
    return False


def _matches_known_percent(target: float, known_values: list[float]) -> bool:
    """Percent match: both relative tolerance AND absolute-pp floor must hold.

    Prevents a fabricated "5%" from matching a real "4.7%" just because they
    differ by <10% relative — 0.3pp absolute floor catches that case.
    """
    for known in known_values:
        absolute_diff = abs(target - known)
        if absolute_diff <= _PERCENT_ABSOLUTE_FLOOR_PP:
            return True
        baseline = abs(known) if known != 0 else 1.0
        if absolute_diff / baseline <= _PERCENT_RELATIVE_TOL:
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
    fraction = intersection / max(len(left_tokens), len(right_tokens))
    # Require a minimum shared token count; otherwise short, generic
    # overlaps ("Apple Q3 results", "Q3 results") appear similar but don't
    # actually anchor the same event.
    if intersection < _HEADLINE_SHARED_TOKENS_MIN:
        return 0.0
    return fraction


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
