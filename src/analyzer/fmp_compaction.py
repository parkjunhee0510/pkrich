from __future__ import annotations

from typing import Any


_MAX_METRIC_VALUE_LENGTH = 80

_FUNDAMENTAL_METRIC_PRIORITY = (
    "industry",
    "roe",
    "roic",
    "gross_margin",
    "gross_margin_trend",
    "operating_margin",
    "operating_margin_trend",
    "fcf_yield",
    "debt_to_equity",
    "current_ratio",
    "net_debt_to_ebitda",
    "annual_dividend",
    "dividend_5y_cagr",
    "dividend_growth_5y",
    "consecutive_increase_years",
    "beta",
)


def compact_fundamental_metrics_for_llm(metrics: Any) -> dict[str, str]:
    """Keep only the FMP-style scalar metrics the prompts can directly use."""
    if not isinstance(metrics, dict):
        return {}

    compacted: dict[str, str] = {}
    for key in _FUNDAMENTAL_METRIC_PRIORITY:
        value = _compact_metric_value(metrics.get(key))
        if value:
            compacted[key] = value
    return compacted


def _compact_metric_value(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    text = str(value).strip()
    if not text or text == "N/A":
        return ""
    if len(text) > _MAX_METRIC_VALUE_LENGTH:
        return text[: _MAX_METRIC_VALUE_LENGTH - 1].rstrip() + "..."
    return text
