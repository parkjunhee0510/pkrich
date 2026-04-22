"""Macro Surprise Index — rolling z-score of recent actual vs consensus releases.

Produces a compact `surprise_score` dict with growth, inflation, and labor
sub-scores in roughly [-2, +2] range. Positive = actual beats consensus in a
direction favorable for risk assets; negative = the opposite.

Non-fatal: returns zeros and low confidence on any failure so callers can
safely merge the result into `macro_context`.
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Category groupings for the final surprise axes.
_CATEGORY_AXES: dict[str, str] = {
    "labor": "labor",
    "inflation": "inflation",
    "rates": "inflation",  # rate decisions map onto inflation axis
    "consumer": "growth",
    "manufacturing": "growth",
    "housing": "growth",
    "trade": "growth",
    "sentiment": "growth",
    "gdp": "growth",
}

# For inflation-category events, a higher actual is risk-off. Flip sign.
_INVERT_SIGN_CATEGORIES = {"inflation", "rates"}

_LOOKBACK_DAYS_DEFAULT = 90


def collect_macro_surprise(
    run_date: date,
    *,
    lookback_days: int = _LOOKBACK_DAYS_DEFAULT,
    upcoming_events: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a `surprise_score` dict computed from recent releases.

    Structure::

        {
          "growth": {"score": float, "samples": int},
          "inflation": {"score": float, "samples": int},
          "labor": {"score": float, "samples": int},
          "composite": float,
          "confidence": "high"|"medium"|"low",
          "window_days": int,
        }
    """
    events = list(upcoming_events or [])

    # Also pull recent past events for a richer window.
    try:
        from src.collector.finnhub import is_finnhub_ready, _fetch_json  # type: ignore
    except Exception:
        is_finnhub_ready = lambda: False  # noqa: E731
        _fetch_json = None  # type: ignore

    past_events: list[dict[str, Any]] = []
    if is_finnhub_ready() and _fetch_json is not None:
        try:
            start = run_date - timedelta(days=lookback_days)
            data = _fetch_json(
                "calendar/economic",
                {"from": start.isoformat(), "to": run_date.isoformat()},
            )
            entries = data.get("economicCalendar", []) if isinstance(data, dict) else []
            past_events = [e for e in entries if isinstance(e, dict)]
        except Exception:
            logger.debug("macro_surprise past fetch failed", exc_info=True)

    axis_values: dict[str, list[float]] = {"growth": [], "inflation": [], "labor": []}
    for raw in list(events) + past_events:
        sample = _extract_sample(raw)
        if sample is None:
            continue
        axis, signed = sample
        axis_values.setdefault(axis, []).append(signed)

    out: dict[str, Any] = {"window_days": lookback_days}
    total_samples = 0
    composite_parts: list[float] = []
    for axis in ("growth", "inflation", "labor"):
        values = axis_values.get(axis, [])
        if not values:
            out[axis] = {"score": 0.0, "samples": 0}
            continue
        score = _bounded_mean_z(values)
        out[axis] = {"score": round(score, 3), "samples": len(values)}
        total_samples += len(values)
        composite_parts.append(score)

    if composite_parts:
        out["composite"] = round(sum(composite_parts) / len(composite_parts), 3)
    else:
        out["composite"] = 0.0

    if total_samples >= 8:
        out["confidence"] = "high"
    elif total_samples >= 3:
        out["confidence"] = "medium"
    else:
        out["confidence"] = "low"
    return out


def _extract_sample(entry: dict[str, Any]) -> tuple[str, float] | None:
    actual = _num(
        entry.get("actual")
        or entry.get("actualValue")
        or entry.get("actualRelease")
    )
    consensus = _num(
        entry.get("consensus")
        or entry.get("estimate")
        or entry.get("forecast")
    )
    if actual is None or consensus is None:
        return None

    category = _infer_category(entry)
    if category is None:
        return None
    axis = _CATEGORY_AXES.get(category)
    if axis is None:
        return None

    denom = max(abs(consensus), 1e-6)
    diff = (actual - consensus) / denom
    # Cap per-sample influence to avoid a single wild print dominating.
    diff = max(-2.0, min(2.0, diff))
    if category in _INVERT_SIGN_CATEGORIES:
        diff = -diff
    return axis, diff


def _infer_category(entry: dict[str, Any]) -> str | None:
    category = str(entry.get("category", "")).strip().lower()
    if category in _CATEGORY_AXES:
        return category

    title = " ".join(
        str(entry.get(k, "")) for k in ("event", "indicator", "release", "title")
    ).lower()
    if not title:
        return None
    if any(k in title for k in ("cpi", "ppi", "inflation", "pce")):
        return "inflation"
    if any(k in title for k in ("nfp", "unemployment", "payroll", "jobs", "unrate")):
        return "labor"
    if any(k in title for k in ("fomc", "interest rate")):
        return "rates"
    if any(k in title for k in ("retail", "sales", "consumer confidence")):
        return "consumer"
    if any(k in title for k in ("ism", "pmi", "manufacturing")):
        return "manufacturing"
    if any(k in title for k in ("housing", "starts", "permits")):
        return "housing"
    if any(k in title for k in ("trade", "export", "import")):
        return "trade"
    if "gdp" in title:
        return "gdp"
    return None


def _num(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in ("", "N/A", "-"):
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _bounded_mean_z(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    # Bound the composite into roughly [-2, +2] regardless of scale.
    return max(-2.0, min(2.0, mean))
