"""EPS and earnings-related helpers extracted from `src/collector/price.py`.

These functions were originally private helpers on the legacy god-module
(`price.py`). Moving them here:
  * Separates earnings/EPS logic from the main price collection pipeline.
  * Allows `yfinance_provider.py` to import them directly without going
    through the legacy `price.py` module.
  * No dependency on `price.py` at module level (avoids circular imports).

All functions follow the same defensive pattern — return "N/A" on
missing/invalid input.
"""
from __future__ import annotations

from typing import Any

from src.collector.helpers.formatters import (
    coerce_finite_float as _coerce_finite_float,
    format_ratio as _format_ratio,
)


# ---------------------------------------------------------------------------
# Internal helpers (not exported but used by the exported functions below)
# ---------------------------------------------------------------------------

def _normalize_field_name(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _tabular_records(value: Any) -> list[dict[str, Any]]:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict("records")
            index_values = list(getattr(value, "index", []))
            normalized_records: list[dict[str, Any]] = []
            for index_value, record in zip(index_values, records, strict=False):
                if isinstance(record, dict):
                    normalized_records.append({"__index__": index_value, **record})
            if normalized_records:
                return normalized_records
        except Exception:
            pass
    return []


def _record_value(record: dict[str, Any], field_names: list[str]) -> Any:
    normalized_record = {_normalize_field_name(key): value for key, value in record.items()}
    for field_name in field_names:
        if field_name in normalized_record:
            return normalized_record[field_name]
    return None


def _earnings_estimate_priority(record: dict[str, Any]) -> int:
    label = str(record.get("__index__") or record.get("period") or record.get("date") or "").strip().lower()
    normalized_label = "".join(character for character in label if character.isalnum() or character in {"+", "-"})
    priority_order = [
        "+1y",
        "nextyear",
        "1y",
        "0y",
        "currentyear",
        "+1q",
        "nextquarter",
        "1q",
        "0q",
        "currentquarter",
    ]
    for index, token in enumerate(priority_order):
        if token and token in normalized_label:
            return index
    return len(priority_order)


def _previous_year_quarter_label(quarter: str) -> str | None:
    if not quarter or "-Q" not in quarter:
        return None
    year_text, quarter_text = quarter.split("-Q", 1)
    try:
        return f"{int(year_text) - 1}-Q{int(quarter_text)}"
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Exported helpers
# ---------------------------------------------------------------------------

def _derive_growth_from_quarterly_financials(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "N/A"
    rows_by_quarter = {
        str(row.get("quarter", "")).strip(): row
        for row in rows
        if isinstance(row, dict)
    }
    for row in rows:
        quarter = str(row.get("quarter", "")).strip()
        prior_quarter = _previous_year_quarter_label(quarter)
        if not prior_quarter:
            continue
        prior_row = rows_by_quarter.get(prior_quarter)
        if not prior_row:
            continue
        current_eps = _coerce_finite_float(row.get("eps"))
        prior_eps = _coerce_finite_float(prior_row.get("eps"))
        if current_eps is None or prior_eps is None or prior_eps == 0:
            continue
        growth = ((current_eps - prior_eps) / abs(prior_eps)) * 100
        return f"{growth:+.2f}% YoY"
    return "N/A"


def _extract_forward_eps_from_analyst_targets(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        return _format_ratio(
            value.get("consensusMeanEps")
            or value.get("meanEps")
            or value.get("targetMeanEps")
        )

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _extract_forward_eps_from_analyst_targets(to_dict())
        except Exception:
            return "N/A"

    return "N/A"


def _extract_forward_eps_from_earnings_estimate(value: Any) -> str:
    records = _tabular_records(value)
    if not records and isinstance(value, dict):
        records = [{"__index__": key, **child} for key, child in value.items() if isinstance(child, dict)]
    if not records:
        return "N/A"

    ranked_records = sorted(records, key=_earnings_estimate_priority)
    for record in ranked_records:
        estimate = _record_value(
            record,
            [
                "avg",
                "average",
                "estimate",
                "epsestimate",
                "consensus",
                "consensuseps",
                "meaneps",
                "consensusmeaneps",
            ],
        )
        formatted = _format_ratio(estimate)
        if formatted != "N/A":
            return formatted
    return "N/A"


__all__ = [
    "_derive_growth_from_quarterly_financials",
    "_extract_forward_eps_from_analyst_targets",
    "_extract_forward_eps_from_earnings_estimate",
]
