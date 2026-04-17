"""Conviction calibration analytics.

Joins signal_tracker rows (conviction, action, regime) with realized forward
returns to measure whether high-conviction calls actually deliver. Exposes two
entry points:

- `bucket_by_conviction_decile(rows)` — decile buckets with mean return, hit
  rate, information ratio, and count per bucket.
- `reliability_diagram(rows)` — predicted-conviction bins vs. realized win
  rate, plus Brier score for calibration quality.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def _parse_float(raw_value: object) -> float | None:
    text = str(raw_value).strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_conviction(raw_value: object) -> float | None:
    value = _parse_float(raw_value)
    if value is None:
        return None
    # Conviction lives on 0-100 scale. Clamp defensively.
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return value


def _evaluated(row: dict[str, str], horizon: int = 5) -> bool:
    return str(row.get(f"evaluated_{horizon}d", "False")).lower() == "true"


def _ticker_neutral_bands(rows: list[dict[str, str]], *, min_samples: int = 5) -> dict[str, float]:
    """Per-ticker 1σ of return_5d for reliability-diagram win classification.

    Mirrors `src.utils.signal_tracker.build_ticker_neutral_bands` (kept local
    to avoid a circular import). Same clamp policy: [0.5%, 5.0%] band.
    """
    by_ticker: dict[str, list[float]] = {}
    for row in rows:
        if not _evaluated(row, horizon=5):
            continue
        ticker = str(row.get("ticker", "")).strip()
        if not ticker:
            continue
        value = _parse_float(row.get("return_5d"))
        if value is None:
            continue
        by_ticker.setdefault(ticker, []).append(value)
    bands: dict[str, float] = {}
    for ticker, values in by_ticker.items():
        if len(values) < min_samples:
            bands[ticker] = 1.0
            continue
        mean_value = sum(values) / len(values)
        variance = sum((v - mean_value) ** 2 for v in values) / (len(values) - 1)
        stdev = math.sqrt(variance) if variance > 0 else 1.0
        bands[ticker] = max(0.5, min(5.0, stdev))
    return bands


def _usable_rows(
    rows: Iterable[dict[str, str]],
    horizon: int = 5,
    *,
    metric: str = "absolute",
) -> list[tuple[float, float, str, float]]:
    """Return (conviction, return_or_alpha, action) triples.

    `metric="absolute"` uses raw `return_Nd` — exposed to survivorship bias
    because the watchlist is curated.
    `metric="alpha"` uses `alpha_5d` (only available for horizon=5 today) —
    watchlist-equal-weight residual return, survivorship-neutral.
    """
    rows_list = list(rows)
    bands = _ticker_neutral_bands(rows_list)
    usable: list[tuple[float, float, str, float]] = []
    return_key = f"return_{horizon}d"
    alpha_key = f"alpha_{horizon}d" if horizon == 5 else None
    for row in rows_list:
        if not _evaluated(row, horizon=horizon):
            continue
        conviction = _parse_conviction(row.get("conviction"))
        if conviction is None:
            continue
        if metric == "alpha" and alpha_key is not None:
            value = _parse_float(row.get(alpha_key))
            if value is None:
                continue
        else:
            value = _parse_float(row.get(return_key))
            if value is None:
                continue
        action = str(row.get("action", "")).strip().lower()
        band = bands.get(str(row.get("ticker", "")).strip(), 1.0)
        usable.append((conviction, value, action, band))
    return usable


def _is_win(action: str, return_pct: float, neutral_band: float = 1.0) -> bool:
    if action == "buy":
        return return_pct > 0
    if action == "avoid":
        return return_pct < 0
    # watch / unknown — treat a near-flat outcome as success. Neutral band
    # defaults to ±1% but callers should pass the ticker's own 1σ to keep
    # the tolerance scale-aware.
    return abs(return_pct) <= neutral_band


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = _mean(values)
    variance = sum((v - mean_value) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def bucket_by_conviction_decile(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    metric: str = "absolute",
) -> dict[str, Any]:
    """Group evaluated signals into conviction deciles and compute performance.

    Returns a payload with:
      - deciles: list of {decile, conviction_range, n, mean_return, hit_rate, ir}
      - total_evaluated: number of rows with both conviction and return
      - horizon: 1|5|20 (days)
    """
    usable = _usable_rows(rows, horizon=horizon, metric=metric)
    if not usable:
        return {
            "status": "insufficient_data",
            "total_evaluated": 0,
            "horizon": horizon,
            "metric": metric,
            "deciles": [],
        }

    # Sort by conviction ascending, split into ~10 equal buckets.
    usable.sort(key=lambda x: x[0])
    n = len(usable)
    buckets = 10 if n >= 10 else max(1, n)

    deciles_out: list[dict[str, Any]] = []
    for i in range(buckets):
        start = (i * n) // buckets
        end = ((i + 1) * n) // buckets
        chunk = usable[start:end]
        if not chunk:
            continue
        convictions = [c for c, _, _, _ in chunk]
        returns = [r for _, r, _, _ in chunk]
        wins = sum(1 for _, r, a, band in chunk if _is_win(a, r, band))
        mean_return = _mean(returns)
        std_return = _stdev(returns)
        ir = (mean_return / std_return) if std_return > 0 else 0.0
        deciles_out.append({
            "decile": i + 1,
            "conviction_min": round(min(convictions), 2),
            "conviction_max": round(max(convictions), 2),
            "n": len(chunk),
            "mean_return": round(mean_return, 3),
            "hit_rate": round(wins / len(chunk), 3),
            "ir": round(ir, 3),
        })

    return {
        "status": "ok",
        "total_evaluated": n,
        "horizon": horizon,
        "metric": metric,
        "deciles": deciles_out,
    }


def reliability_diagram(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    bins: int = 10,
) -> dict[str, Any]:
    """Build a calibration curve: predicted conviction vs. realized win rate.

    - Predicted probability = conviction / 100.
    - Realized outcome = 1 if win (per action/_is_win), else 0.
    - Brier score = mean((p - outcome)^2). Lower is better; 0 is perfect.
    """
    usable = _usable_rows(rows, horizon=horizon)
    if not usable:
        return {
            "status": "insufficient_data",
            "total_evaluated": 0,
            "horizon": horizon,
            "bins": [],
            "brier_score": None,
        }

    predictions: list[float] = []
    outcomes: list[int] = []
    for conviction, return_pct, action, band in usable:
        predictions.append(conviction / 100.0)
        outcomes.append(1 if _is_win(action, return_pct, band) else 0)

    # Brier score
    brier = sum((p - o) ** 2 for p, o in zip(predictions, outcomes, strict=False)) / len(predictions)

    # Bin by predicted probability into equal-width bins over [0, 1].
    bin_width = 1.0 / bins
    bin_buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, o in zip(predictions, outcomes, strict=False):
        idx = min(int(p / bin_width), bins - 1)
        bin_buckets[idx].append((p, o))

    bins_out: list[dict[str, Any]] = []
    for i, bucket in enumerate(bin_buckets):
        if not bucket:
            continue
        mean_predicted = _mean([p for p, _ in bucket])
        mean_realized = _mean([o for _, o in bucket])
        bins_out.append({
            "bin": i + 1,
            "predicted_min": round(i * bin_width, 2),
            "predicted_max": round((i + 1) * bin_width, 2),
            "predicted": round(mean_predicted, 3),
            "realized": round(mean_realized, 3),
            "n": len(bucket),
        })

    return {
        "status": "ok",
        "total_evaluated": len(usable),
        "horizon": horizon,
        "brier_score": round(brier, 4),
        "bins": bins_out,
    }


def brier_drift(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    window_days: int = 30,
) -> dict[str, Any]:
    """Rolling Brier score over signal_date to detect calibration drift.

    For each evaluated signal date, compute the Brier score across all
    signals in a trailing `window_days` window. Rising Brier ⇒ calibration
    is degrading (regime shift, model drift, stale weights).

    Trend: OLS slope of Brier vs. day-index over the last `window_days*2`
    points. Positive slope = drift.
    """
    rows_list = list(rows)
    bands = _ticker_neutral_bands(rows_list)

    # Collect (date_str, predicted, outcome) for evaluated rows.
    dated: list[tuple[str, float, int]] = []
    for row in rows_list:
        if not _evaluated(row, horizon=horizon):
            continue
        conviction = _parse_conviction(row.get("conviction"))
        if conviction is None:
            continue
        ret = _parse_float(row.get(f"return_{horizon}d"))
        if ret is None:
            continue
        signal_date = str(row.get("signal_date", "")).strip()
        if not signal_date:
            continue
        action = str(row.get("action", "")).strip().lower()
        band = bands.get(str(row.get("ticker", "")).strip(), 1.0)
        outcome = 1 if _is_win(action, ret, band) else 0
        dated.append((signal_date, conviction / 100.0, outcome))

    if len(dated) < 10:
        return {
            "status": "insufficient_data",
            "horizon": horizon,
            "window_days": window_days,
            "series": [],
            "trend_slope": None,
            "latest_brier": None,
        }

    dated.sort(key=lambda triple: triple[0])
    unique_dates = sorted({d for d, _, _ in dated})

    # For each unique date, compute Brier over the trailing window.
    from datetime import date as _date

    def _parse_iso(s: str) -> _date | None:
        try:
            return _date.fromisoformat(s)
        except ValueError:
            return None

    series: list[dict[str, Any]] = []
    for end_str in unique_dates:
        end_date = _parse_iso(end_str)
        if end_date is None:
            continue
        window_items: list[tuple[float, int]] = []
        for d_str, p, o in dated:
            d = _parse_iso(d_str)
            if d is None:
                continue
            if d > end_date:
                break  # sorted ascending — can stop
            delta_days = (end_date - d).days
            if delta_days <= window_days:
                window_items.append((p, o))
        if len(window_items) < 5:
            continue
        brier = sum((p - o) ** 2 for p, o in window_items) / len(window_items)
        series.append({
            "date": end_str,
            "brier": round(brier, 4),
            "n": len(window_items),
        })

    # OLS slope of Brier over point index (last 2×window_days equivalent).
    trend_slope: float | None = None
    if len(series) >= 3:
        tail = series[-min(len(series), window_days * 2):]
        xs = list(range(len(tail)))
        ys = [pt["brier"] for pt in tail]
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=False))
        den = sum((x - x_mean) ** 2 for x in xs)
        trend_slope = round(num / den, 6) if den > 0 else 0.0

    return {
        "status": "ok",
        "horizon": horizon,
        "window_days": window_days,
        "series": series,
        "trend_slope": trend_slope,
        "latest_brier": series[-1]["brier"] if series else None,
        "drift_alert": (
            trend_slope is not None and trend_slope > 0.002
        ),
    }


def build_calibration_payload(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> dict[str, Any]:
    """Convenience wrapper — produce the shape the Admin page consumes.

    Includes both absolute and alpha (watchlist-relative) decile buckets so
    the Admin UI can surface the survivorship-adjusted view. `alpha_buckets`
    is populated only for horizon=5 (where `alpha_5d` exists).
    """
    rows_list = list(rows)
    payload: dict[str, Any] = {
        "horizon": horizon,
        "decile_buckets": bucket_by_conviction_decile(rows_list, horizon=horizon),
        "reliability": reliability_diagram(rows_list, horizon=horizon),
    }
    if horizon == 5:
        payload["alpha_buckets"] = bucket_by_conviction_decile(
            rows_list, horizon=horizon, metric="alpha"
        )
    payload["drift"] = brier_drift(rows_list, horizon=horizon)
    return payload
