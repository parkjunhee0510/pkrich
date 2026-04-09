from __future__ import annotations

import re

_COMPACT_NUMBER_PATTERN = re.compile(r"^\s*([-+]?\d[\d,]*\.?\d*)([TBM]?)\s*$", re.IGNORECASE)
_QUARTER_PATTERN = re.compile(r"^\s*(\d{4})-Q([1-4])\s*$")
_NUMBER_SUFFIX_MULTIPLIERS = {
    "": 1.0,
    "M": 1_000_000.0,
    "B": 1_000_000_000.0,
    "T": 1_000_000_000_000.0,
}


def build_quarterly_financial_display_rows(
    rows: list[dict[str, str]],
    *,
    limit: int = 4,
) -> list[dict[str, str]]:
    if not rows:
        return []

    prior_year_rows = {
        str(row.get("quarter", "")).strip(): row
        for row in rows
        if isinstance(row, dict)
    }

    display_rows: list[dict[str, str]] = []
    for row in rows[:limit]:
        quarter = str(row.get("quarter", "N/A")).strip() or "N/A"
        prior_year_key = _previous_year_quarter(quarter)
        prior_row = prior_year_rows.get(prior_year_key) if prior_year_key else None

        display_rows.append(
            {
                "quarter": quarter,
                "revenue": str(row.get("revenue", "N/A")),
                "operating_income": str(row.get("operating_income", "N/A")),
                "eps": str(row.get("eps", "N/A")),
                "revenue_yoy": _format_yoy(row.get("revenue"), prior_row.get("revenue") if prior_row else None),
                "operating_income_yoy": _format_yoy(
                    row.get("operating_income"),
                    prior_row.get("operating_income") if prior_row else None,
                ),
                "eps_yoy": _format_yoy(row.get("eps"), prior_row.get("eps") if prior_row else None),
            }
        )

    return display_rows


def _previous_year_quarter(quarter: str) -> str | None:
    match = _QUARTER_PATTERN.match(quarter)
    if not match:
        return None
    year = int(match.group(1)) - 1
    quarter_number = match.group(2)
    return f"{year}-Q{quarter_number}"


def _format_yoy(current_value: object, prior_value: object) -> str:
    current = _parse_compact_number(current_value)
    prior = _parse_compact_number(prior_value)
    if current is None or prior is None or prior == 0:
        return ""
    yoy = ((current - prior) / abs(prior)) * 100
    return f"{yoy:+.1f}% YoY"


def _parse_compact_number(value: object) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text or text == "N/A":
        return None

    match = _COMPACT_NUMBER_PATTERN.match(text)
    if not match:
        return None

    try:
        numeric_value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None

    suffix = match.group(2).upper()
    return numeric_value * _NUMBER_SUFFIX_MULTIPLIERS.get(suffix, 1.0)
