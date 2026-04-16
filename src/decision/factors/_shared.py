from __future__ import annotations

import re
from typing import Any


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def score_confidence(*values: Any) -> float:
    present = sum(1 for value in values if value not in (None, "", "N/A", {}, []))
    if present >= max(1, len(values) - 1):
        return 0.9
    if present >= max(1, len(values) // 2):
        return 0.6
    return 0.3


def clamp_score(value: float, low: int, high: int) -> int:
    return int(max(low, min(high, round(value))))
