from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.utils.model_config import ModelProfile


@dataclass(frozen=True)
class UsageCost:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    total_tokens: int
    estimated_cost_usd: float


def calculate_response_cost(response: Any, model_profile: ModelProfile) -> UsageCost:
    usage = getattr(response, 'usage', None)
    if usage is None:
        return UsageCost(0, 0, 0, 0, 0.0)

    input_tokens = _read_int(usage, 'input_tokens')
    output_tokens = _read_int(usage, 'output_tokens')
    total_tokens = _read_int(usage, 'total_tokens') or (input_tokens + output_tokens)
    input_details = _read_value(usage, 'input_tokens_details')
    cached_input_tokens = _read_int(input_details, 'cached_tokens') or _read_int(input_details, 'cache_read_input_tokens')
    uncached_input_tokens = max(input_tokens - cached_input_tokens, 0)

    estimated_cost = (
        (uncached_input_tokens * model_profile.input_cost_per_1m_tokens)
        + (cached_input_tokens * model_profile.cached_input_cost_per_1m_tokens)
        + (output_tokens * model_profile.output_cost_per_1m_tokens)
    ) / 1_000_000

    return UsageCost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=round(estimated_cost, 8),
    )


def _read_int(source: Any, key: str) -> int:
    value = _read_value(source, key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_value(source: Any, key: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)
