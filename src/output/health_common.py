"""Shared helpers for output health validators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputHealthIssue:
    code: str
    path: str
    detail: str


def _load_json_object(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_non_negative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_non_negative_int_mapping(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(key, str) and _is_non_negative_int(count) for key, count in value.items())


def _is_string_mapping(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(key, str) and isinstance(item, str) for key, item in value.items())


def _is_probability(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0.0 <= float(value) <= 1.0


def _is_probability_or_none(value: object) -> bool:
    return value is None or _is_probability(value)


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _is_number_or_none(value: object) -> bool:
    return value is None or _is_number(value)


def _is_non_negative_number(value: object) -> bool:
    return _is_number(value) and float(value) >= 0.0


def _is_non_negative_number_or_none(value: object) -> bool:
    return value is None or _is_non_negative_number(value)


def _is_correlation(value: object) -> bool:
    return _is_number(value) and -1.0 <= float(value) <= 1.0


def _is_correlation_or_none(value: object) -> bool:
    return value is None or _is_correlation(value)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
