"""Configuration for the collector-owned search evidence layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.utils.config import load_yaml_mapping


DEFAULT_QUERY_TEMPLATES: tuple[str, ...] = (
    "{ticker} latest earnings revenue guidance",
    "{ticker} recent risks demand backlog valuation",
)


@dataclass(frozen=True)
class SearchEvidenceConfig:
    mode: str = "openai"
    provider: str = "openai"
    model_profile: str = "standard"
    tool_type: str = "web_search"
    max_search_tickers_per_run: int = 5
    max_queries_per_ticker: int = 2
    cache_ttl_hours: int = 24
    requests_per_minute: int = 6
    tokens_per_minute: int = 60_000
    rate_limit_timeout_seconds: float = 5.0
    estimated_input_tokens_per_query: int = 900
    estimated_output_tokens_per_query: int = 700
    query_templates: tuple[str, ...] = DEFAULT_QUERY_TEMPLATES


def load_search_evidence_config(path: str = "config/search_evidence.yaml") -> SearchEvidenceConfig:
    raw = load_yaml_mapping(path, optional=True)
    raw = _apply_env_overrides(raw)
    return search_evidence_config_from_mapping(raw)


def search_evidence_config_from_mapping(raw: dict[str, Any] | None) -> SearchEvidenceConfig:
    raw = raw or {}
    return SearchEvidenceConfig(
        mode=_choice(raw.get("mode"), {"cache", "openai", "off"}, default="openai"),
        provider=_choice(raw.get("provider"), {"openai"}, default="openai"),
        model_profile=_text(raw.get("model_profile"), default="standard"),
        tool_type=_text(raw.get("tool_type"), default="web_search"),
        max_search_tickers_per_run=_positive_int(raw.get("max_search_tickers_per_run"), default=5),
        max_queries_per_ticker=_positive_int(raw.get("max_queries_per_ticker"), default=2),
        cache_ttl_hours=_positive_int(raw.get("cache_ttl_hours"), default=24),
        requests_per_minute=_positive_int(raw.get("requests_per_minute"), default=6),
        tokens_per_minute=_positive_int(raw.get("tokens_per_minute"), default=60_000),
        rate_limit_timeout_seconds=_positive_float(raw.get("rate_limit_timeout_seconds"), default=5.0),
        estimated_input_tokens_per_query=_positive_int(raw.get("estimated_input_tokens_per_query"), default=900),
        estimated_output_tokens_per_query=_positive_int(raw.get("estimated_output_tokens_per_query"), default=700),
        query_templates=_string_tuple(raw.get("query_templates"), default=DEFAULT_QUERY_TEMPLATES),
    )


def _choice(value: Any, allowed: set[str], *, default: str) -> str:
    text = str(value or default).strip().lower()
    return text if text in allowed else default


def _apply_env_overrides(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(raw or {})
    overrides = {
        "SEARCH_EVIDENCE_MODE": "mode",
        "SEARCH_EVIDENCE_MAX_TICKERS_PER_RUN": "max_search_tickers_per_run",
        "SEARCH_EVIDENCE_MAX_QUERIES_PER_TICKER": "max_queries_per_ticker",
    }
    for env_name, config_key in overrides.items():
        value = os.getenv(env_name)
        if value is not None and value.strip():
            merged[config_key] = value.strip()
    return merged


def _text(value: Any, *, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _positive_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _string_tuple(value: Any, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return default
    normalized = tuple(str(item).strip() for item in value if str(item).strip())
    return normalized or default
