"""Output-only performance analytics for tracked signals."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any

HORIZONS = (1, 5, 20)
BUCKETS = (
    ("0_35", 0, 35),
    ("35_50", 35, 50),
    ("50_65", 50, 65),
    ("65_80", 65, 80),
    ("80_100", 80, 100),
)
_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def build_signal_performance(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    result = {
        action: {f"{horizon}d": _empty_window() for horizon in HORIZONS}
        for action in ("buy", "watch", "avoid", "unknown")
    }
    for action_name in result:
        action_rows = [row for row in rows if _action(row) == action_name]
        for horizon in HORIZONS:
            result[action_name][f"{horizon}d"] = _window_metrics(action_rows, horizon, action_name)
    return result


def build_conviction_calibration(rows: list[dict[str, str]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {
        name: {
            "sample_count": 0,
            "action_counts": {},
            "avg_return_1d": None,
            "avg_return_5d": None,
            "avg_return_20d": None,
            "buy_win_rate": None,
            "avoid_win_rate": None,
        }
        for name, _, _ in BUCKETS
    }
    bucket_rows: dict[str, list[dict[str, str]]] = {name: [] for name, _, _ in BUCKETS}
    for row in rows:
        conviction = _parse_float(row.get("conviction"))
        if conviction is None:
            continue
        bucket_rows[_bucket_name(conviction)].append(row)

    for name, grouped_rows in bucket_rows.items():
        action_counts = Counter(_action(row) for row in grouped_rows)
        buckets[name]["sample_count"] = len(grouped_rows)
        buckets[name]["action_counts"] = dict(sorted(action_counts.items()))
        for horizon in HORIZONS:
            usable = [
                value
                for value in (_return_value(row, horizon) for row in grouped_rows)
                if value is not None
            ]
            buckets[name][f"avg_return_{horizon}d"] = (
                round(sum(usable) / len(usable), 4) if usable else None
            )
        buckets[name]["buy_win_rate"] = _directional_rate(grouped_rows, "buy", 5)
        buckets[name]["avoid_win_rate"] = _directional_rate(grouped_rows, "avoid", 5)

    return {
        "status": "observational",
        "bucket_edges": [name for name, _, _ in BUCKETS],
        "buckets": buckets,
    }


def build_regime_performance(rows: list[dict[str, str]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[_regime(row)][_action(row)].append(row)

    result: dict[str, Any] = {}
    for regime_name in sorted(grouped):
        result[regime_name] = {}
        for action_name in sorted(grouped[regime_name]):
            result[regime_name][action_name] = {
                f"{horizon}d": _window_metrics(grouped[regime_name][action_name], horizon, action_name)
                for horizon in HORIZONS
            }
    return result


def build_factor_attribution(rows: list[dict[str, str]]) -> dict[str, Any]:
    factor_samples: dict[str, list[tuple[float, dict[str, str]]]] = defaultdict(list)
    missing_factor_sample_count = 0
    for row in rows:
        factors = _parse_factors(row.get("factors_json"))
        if not factors:
            missing_factor_sample_count += 1
            continue
        for factor, score in factors.items():
            factor_samples[factor].append((score, row))

    factor_payload: dict[str, Any] = {}
    for factor in sorted(factor_samples):
        samples = factor_samples[factor]
        scores = [score for score, _ in samples]
        rows_for_factor = [row for _, row in samples]
        usable_5d = [
            value
            for value in (_return_value(row, 5) for row in rows_for_factor)
            if value is not None
        ]
        usable_20d = [
            value
            for value in (_return_value(row, 20) for row in rows_for_factor)
            if value is not None
        ]
        factor_payload[factor] = {
            "sample_count": len(samples),
            "avg_score": round(sum(scores) / len(scores), 4) if scores else None,
            "positive_score_count": sum(1 for score in scores if score > 0),
            "negative_score_count": sum(1 for score in scores if score < 0),
            "avg_forward_return_5d": round(sum(usable_5d) / len(usable_5d), 4) if usable_5d else None,
            "avg_forward_return_20d": round(sum(usable_20d) / len(usable_20d), 4) if usable_20d else None,
            "best_action_context": _action_context(rows_for_factor, reverse=True),
            "worst_action_context": _action_context(rows_for_factor, reverse=False),
        }

    return {
        "status": "observed_association",
        "missing_factor_sample_count": missing_factor_sample_count,
        "factors": factor_payload,
    }


def _window_metrics(rows: list[dict[str, str]], horizon: int, action_name: str) -> dict[str, Any]:
    values: list[float] = []
    missing_count = 0
    outcomes: Counter[str] = Counter()
    distribution: Counter[str] = Counter({"positive": 0, "negative": 0, "flat": 0})
    wins = 0
    losses = 0

    for row in rows:
        value = _return_value(row, horizon)
        if value is None:
            missing_count += 1
            continue
        values.append(value)
        label = str(row.get("barrier_label", "") or "unknown").strip() or "unknown"
        outcomes[label] += 1
        if value > 0:
            distribution["positive"] += 1
        elif value < 0:
            distribution["negative"] += 1
        else:
            distribution["flat"] += 1

        if action_name == "buy":
            wins += 1 if value > 0 else 0
            losses += 1 if value <= 0 else 0
        elif action_name == "avoid":
            wins += 1 if value <= 0 else 0
            losses += 1 if value > 0 else 0

    completed = len(values)
    directional_win_rate = None
    win_rate = None
    loss_rate = None
    if action_name in {"buy", "avoid"} and completed:
        directional_win_rate = round(wins / completed, 4)
        win_rate = directional_win_rate
        loss_rate = round(losses / completed, 4)

    return {
        "sample_count": len(rows),
        "completed_count": completed,
        "avg_return": round(sum(values) / completed, 4) if completed else None,
        "median_return": round(float(median(values)), 4) if completed else None,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "directional_win_rate": directional_win_rate,
        "missing_count": missing_count,
        "return_distribution": dict(distribution),
        "triple_barrier_outcomes": dict(sorted(outcomes.items())),
    }


def _bucket_name(conviction: float) -> str:
    clamped = max(0.0, min(100.0, conviction))
    for name, low, high in BUCKETS:
        if low <= clamped < high:
            return name
    return "80_100"


def _directional_rate(rows: list[dict[str, str]], action_name: str, horizon: int) -> float | None:
    action_rows = [row for row in rows if _action(row) == action_name]
    usable = [
        value
        for value in (_return_value(row, horizon) for row in action_rows)
        if value is not None
    ]
    if not usable:
        return None
    if action_name == "buy":
        wins = sum(1 for value in usable if value > 0)
    elif action_name == "avoid":
        wins = sum(1 for value in usable if value <= 0)
    else:
        return None
    return round(wins / len(usable), 4)


def _action_context(rows: list[dict[str, str]], *, reverse: bool) -> dict[str, Any]:
    by_action: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _return_value(row, 5)
        if value is not None:
            by_action[_action(row)].append(value)
    contexts = [
        {
            "action": action,
            "sample_count": len(values),
            "avg_return_5d": round(sum(values) / len(values), 4),
        }
        for action, values in by_action.items()
        if values
    ]
    if not contexts:
        return {"action": "", "sample_count": 0, "avg_return_5d": None}
    return sorted(contexts, key=lambda item: item["avg_return_5d"], reverse=reverse)[0]


def _empty_window() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "completed_count": 0,
        "avg_return": None,
        "median_return": None,
        "win_rate": None,
        "loss_rate": None,
        "directional_win_rate": None,
        "missing_count": 0,
        "return_distribution": {"positive": 0, "negative": 0, "flat": 0},
        "triple_barrier_outcomes": {},
    }


def _parse_float(raw: object) -> float | None:
    text = str(raw or "").strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _is_evaluated(row: dict[str, str], horizon: int) -> bool:
    return str(row.get(f"evaluated_{horizon}d", "False")).strip().lower() == "true"


def _return_value(row: dict[str, str], horizon: int) -> float | None:
    if not _is_evaluated(row, horizon):
        return None
    return _parse_float(row.get(f"return_{horizon}d"))


def _action(row: dict[str, str]) -> str:
    action = str(row.get("action", "") or "").strip().lower()
    return action if action in {"buy", "watch", "avoid"} else "unknown"


def _regime(row: dict[str, str]) -> str:
    return str(row.get("regime", "") or "unknown").strip().lower() or "unknown"


def _parse_factors(raw: object) -> dict[str, float]:
    try:
        payload = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in payload.items():
        parsed = _parse_float(value)
        if parsed is not None:
            result[str(key)] = parsed
    return result
