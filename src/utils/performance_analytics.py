from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any


HORIZONS = (1, 5, 20)
BUCKETS = (
    ("0_35", 0.0, 35.0),
    ("35_50", 35.0, 50.0),
    ("50_65", 50.0, 65.0),
    ("65_80", 65.0, 80.0),
    ("80_100", 80.0, 100.0),
)

_ACTIONS = ("buy", "watch", "avoid", "unknown")
_FLOAT_PATTERN = re.compile(
    r"[-+]?(?:(?:\d{1,3}(?:,\d{3})+)|\d+)(?:\.\d+)?\s*%?"
)


def _parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        if parsed != parsed or parsed in (float("inf"), float("-inf")):
            return None
        return parsed

    text = str(value).strip()
    if not text or text.lower() in {"n/a", "na", "nan", "none", "null", "--"}:
        return None

    match = _FLOAT_PATTERN.fullmatch(text)
    if match is None:
        return None

    try:
        return float(match.group(0).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def _is_evaluated(row: dict[str, Any], horizon: int) -> bool:
    value = row.get(f"evaluated_{horizon}d")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False

    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _return_value(row: dict[str, Any], horizon: int) -> float | None:
    if not _is_evaluated(row, horizon):
        return None
    return _parse_float(row.get(f"return_{horizon}d"))


def _action(row: dict[str, Any]) -> str:
    action = str(row.get("action", "")).strip().lower()
    if action in {"buy", "watch", "avoid"}:
        return action
    return "unknown"


def _regime(row: dict[str, Any]) -> str:
    raw_regime = row.get("regime")
    if not isinstance(raw_regime, str):
        return "unknown"

    regime = raw_regime.strip().lower()
    if regime in {"n/a", "na", "none", "null"}:
        return "unknown"
    return regime or "unknown"


def _parse_factors(row: dict[str, Any]) -> dict[str, float]:
    raw_factors = row.get("factors_json")
    if not raw_factors:
        return {}

    try:
        parsed = json.loads(str(raw_factors))
    except (TypeError, ValueError):
        return {}

    if not isinstance(parsed, dict):
        return {}

    factors: dict[str, float] = {}
    for name, value in parsed.items():
        factor_value = _parse_float(value)
        if factor_value is not None:
            factors[str(name)] = factor_value
    return factors


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _average_return(rows: list[dict[str, Any]], horizon: int) -> float | None:
    returns = [
        realized_return
        for row in rows
        if (realized_return := _return_value(row, horizon)) is not None
    ]
    return _average(returns)


def _directional_win_rate(
    rows: list[dict[str, Any]],
    horizon: int,
    action_name: str,
) -> float | None:
    completed = [
        realized_return
        for row in rows
        if _action(row) == action_name
        and (realized_return := _return_value(row, horizon)) is not None
    ]
    if not completed:
        return None

    if action_name == "buy":
        wins = sum(1 for realized_return in completed if realized_return > 0)
    elif action_name == "avoid":
        wins = sum(1 for realized_return in completed if realized_return <= 0)
    else:
        return None

    return round(wins / len(completed), 4)


def _bucket_for_conviction(conviction: float) -> str | None:
    for index, (bucket_name, lower_bound, upper_bound) in enumerate(BUCKETS):
        is_last_bucket = index == len(BUCKETS) - 1
        if conviction >= lower_bound and (
            conviction < upper_bound or (is_last_bucket and conviction <= upper_bound)
        ):
            return bucket_name
    return None


def _empty_window() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "completed_count": 0,
        "missing_count": 0,
        "avg_return": None,
        "median_return": None,
        "win_rate": None,
        "loss_rate": None,
        "directional_win_rate": None,
        "return_distribution": {
            "positive": 0,
            "negative": 0,
            "flat": 0,
        },
        "triple_barrier_outcomes": {},
    }


def build_signal_performance(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_action(row)].append(row)

    payload: dict[str, dict[str, dict[str, Any]]] = {}
    for action_name in _ACTIONS:
        action_rows = grouped.get(action_name, [])
        payload[action_name] = {
            f"{horizon}d": _window_metrics(action_rows, horizon, action_name)
            for horizon in HORIZONS
        }
    return payload


def _window_metrics(
    rows: list[dict[str, Any]],
    horizon: int,
    action_name: str,
) -> dict[str, Any]:
    metrics = _empty_window()
    metrics["sample_count"] = len(rows)

    returns: list[float] = []
    wins = 0
    losses = 0
    distribution = Counter({"positive": 0, "negative": 0, "flat": 0})
    barrier_outcomes: Counter[str] = Counter()

    for row in rows:
        realized_return = _return_value(row, horizon)
        if realized_return is None:
            metrics["missing_count"] += 1
            continue

        returns.append(realized_return)
        if realized_return > 0:
            distribution["positive"] += 1
        elif realized_return < 0:
            distribution["negative"] += 1
        else:
            distribution["flat"] += 1

        raw_barrier_label = row.get("barrier_label")
        barrier_label = raw_barrier_label.strip() if isinstance(raw_barrier_label, str) else ""
        if barrier_label:
            barrier_outcomes[barrier_label] += 1

        if action_name == "buy":
            if realized_return > 0:
                wins += 1
            else:
                losses += 1
        elif action_name == "avoid":
            if realized_return <= 0:
                wins += 1
            else:
                losses += 1

    completed_count = len(returns)
    metrics["completed_count"] = completed_count
    metrics["return_distribution"] = dict(distribution)
    metrics["triple_barrier_outcomes"] = dict(barrier_outcomes)

    if completed_count == 0:
        return metrics

    metrics["avg_return"] = round(sum(returns) / completed_count, 4)
    metrics["median_return"] = round(median(returns), 4)

    if action_name in {"buy", "avoid"}:
        metrics["win_rate"] = round(wins / completed_count, 4)
        metrics["loss_rate"] = round(losses / completed_count, 4)
        metrics["directional_win_rate"] = metrics["win_rate"]

    return metrics


def build_conviction_calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_rows: dict[str, list[dict[str, Any]]] = {
        bucket_name: [] for bucket_name, _lower_bound, _upper_bound in BUCKETS
    }
    for row in rows:
        conviction = _parse_float(row.get("conviction"))
        if conviction is None:
            continue

        bucket_name = _bucket_for_conviction(conviction)
        if bucket_name is not None:
            bucket_rows[bucket_name].append(row)

    buckets: dict[str, Any] = {}
    for bucket_name, _lower_bound, _upper_bound in BUCKETS:
        rows_in_bucket = bucket_rows[bucket_name]
        action_counts = Counter({_action_name: 0 for _action_name in _ACTIONS})
        action_counts.update(_action(row) for row in rows_in_bucket)

        buckets[bucket_name] = {
            "sample_count": len(rows_in_bucket),
            "action_counts": dict(action_counts),
            "avg_return_1d": _average_return(rows_in_bucket, 1),
            "avg_return_5d": _average_return(rows_in_bucket, 5),
            "avg_return_20d": _average_return(rows_in_bucket, 20),
            "buy_win_rate": _directional_win_rate(rows_in_bucket, 5, "buy"),
            "avoid_win_rate": _directional_win_rate(rows_in_bucket, 5, "avoid"),
        }

    return {
        "status": "observational",
        "buckets": buckets,
    }


def build_regime_performance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        grouped[_regime(row)][_action(row)].append(row)

    payload: dict[str, Any] = {}
    for regime_name in sorted(grouped):
        payload[regime_name] = {}
        for action_name in _ACTIONS:
            action_rows = grouped[regime_name].get(action_name, [])
            payload[regime_name][action_name] = {
                f"{horizon}d": _window_metrics(action_rows, horizon, action_name)
                for horizon in HORIZONS
            }
    return payload


def build_factor_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    factor_samples: dict[str, list[tuple[dict[str, Any], float]]] = defaultdict(list)
    missing_factor_sample_count = 0

    for row in rows:
        factors = _parse_factors(row)
        if not factors:
            missing_factor_sample_count += 1
            continue

        for factor_name, score in factors.items():
            factor_samples[factor_name].append((row, score))

    factors_payload: dict[str, Any] = {}
    for factor_name in sorted(factor_samples):
        samples = factor_samples[factor_name]
        scores = [score for _row, score in samples]
        sample_rows = [row for row, _score in samples]

        action_contexts = [
            _factor_action_context(action_name, samples)
            for action_name in _ACTIONS
            if any(_action(row) == action_name for row, _score in samples)
        ]
        ranked_contexts = [
            context
            for context in action_contexts
            if context["avg_forward_return_5d"] is not None
        ]

        factors_payload[factor_name] = {
            "sample_count": len(samples),
            "avg_score": _average(scores),
            "positive_score_count": sum(1 for score in scores if score > 0),
            "negative_score_count": sum(1 for score in scores if score < 0),
            "avg_forward_return_5d": _average_return(sample_rows, 5),
            "avg_forward_return_20d": _average_return(sample_rows, 20),
            "best_action_context": _select_action_context(ranked_contexts, best=True),
            "worst_action_context": _select_action_context(ranked_contexts, best=False),
        }

    return {
        "status": "observed_association",
        "missing_factor_sample_count": missing_factor_sample_count,
        "factors": factors_payload,
    }


def _factor_action_context(
    action_name: str,
    samples: list[tuple[dict[str, Any], float]],
) -> dict[str, Any]:
    action_samples = [
        (row, score) for row, score in samples if _action(row) == action_name
    ]
    action_rows = [row for row, _score in action_samples]
    action_scores = [score for _row, score in action_samples]

    return {
        "action": action_name,
        "sample_count": len(action_samples),
        "avg_score": _average(action_scores),
        "avg_forward_return_5d": _average_return(action_rows, 5),
        "avg_forward_return_20d": _average_return(action_rows, 20),
    }


def _select_action_context(
    contexts: list[dict[str, Any]],
    *,
    best: bool,
) -> dict[str, Any] | None:
    if not contexts:
        return None

    action_order = {action_name: index for index, action_name in enumerate(_ACTIONS)}
    return sorted(
        contexts,
        key=lambda context: (
            context["avg_forward_return_5d"],
            -action_order.get(context["action"], len(_ACTIONS)),
        ),
        reverse=best,
    )[0]
