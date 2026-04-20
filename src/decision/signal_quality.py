"""Signal-quality metrics (Phase A — measurement first).

Extends `factor_audit` along the **time** and **horizon** axes:

1. **IC decay** — Spearman IC of each factor against realized 1D / 5D / 20D
   returns. A healthy factor should show monotonic decay
   (|IC_1D| > |IC_5D| > |IC_20D|) — flat/inverted curves flag regime
   mismatch or leakage.
2. **Rolling IC** — 90-day rolling Spearman IC per factor to surface
   regime-dependent factor fatigue (a factor with strong lifetime IC but
   negative trailing-90d IC is dying).
3. **Kelly fraction by direction** — hit rate × payoff asymmetry →
   half-Kelly fraction. Feeds position-sizing guard in the decision layer.
4. **Signal turnover** — day-over-day Jaccard change of the active signal
   set. Very high turnover means the system is whipsawing; very low means
   it's stuck.

All functions return defensively-typed dicts with `status: "ok"` or
`status: "insufficient_data"` so the frontend can render without crashing
when signal volume is low.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from src.decision.factor_audit import (
    MIN_SAMPLE_SIZE,
    _parse_factors,
    _parse_float,
    _spearman,
)

HORIZONS: tuple[int, ...] = (1, 5, 20)
ROLLING_WINDOW_DAYS = 90
ROLLING_STEP_DAYS = 15
MIN_ROWS_PER_WINDOW = 10
MIN_ROWS_FOR_KELLY = 20
KELLY_HAIRCUT = 0.5  # half-Kelly — full Kelly is notoriously aggressive


def _parse_iso_date(raw: object) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _evaluated_rows(
    rows: Iterable[dict[str, str]], horizon: int
) -> list[tuple[date, dict[str, float], float]]:
    """(signal_date, factors, return) tuples where the horizon is evaluated."""
    usable: list[tuple[date, dict[str, float], float]] = []
    for row in rows:
        if str(row.get(f"evaluated_{horizon}d", "False")).lower() != "true":
            continue
        factors = _parse_factors(row.get("factors_json"))
        if not factors:
            continue
        ret = _parse_float(row.get(f"return_{horizon}d"))
        signal_date = _parse_iso_date(row.get("signal_date"))
        if ret is None or signal_date is None:
            continue
        usable.append((signal_date, factors, ret))
    return usable


def compute_ic_decay(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    """IC at 1D / 5D / 20D per factor. Healthy curve = monotonic decay."""
    rows_list = list(rows)
    per_horizon: dict[int, list[tuple[date, dict[str, float], float]]] = {
        h: _evaluated_rows(rows_list, h) for h in HORIZONS
    }

    # factor coverage across all horizons
    factor_names: set[str] = set()
    for bucket in per_horizon.values():
        for _, factors, _ in bucket:
            factor_names.update(factors.keys())

    if all(len(bucket) < MIN_SAMPLE_SIZE for bucket in per_horizon.values()):
        return {
            "status": "insufficient_data",
            "sample_sizes": {f"{h}d": len(per_horizon[h]) for h in HORIZONS},
            "factors": [],
        }

    results: list[dict[str, Any]] = []
    for name in sorted(factor_names):
        horizon_ic: dict[str, float | None] = {}
        horizon_n: dict[str, int] = {}
        for h in HORIZONS:
            xs: list[float] = []
            ys: list[float] = []
            for _, factors, ret in per_horizon[h]:
                if name in factors:
                    xs.append(factors[name])
                    ys.append(ret)
            if len(xs) < MIN_SAMPLE_SIZE:
                horizon_ic[f"{h}d"] = None
                horizon_n[f"{h}d"] = len(xs)
                continue
            ic = _spearman(xs, ys)
            horizon_ic[f"{h}d"] = round(ic, 3) if ic is not None else None
            horizon_n[f"{h}d"] = len(xs)

        ics = [horizon_ic[f"{h}d"] for h in HORIZONS]
        if all(v is None for v in ics):
            continue

        # Monotonic decay check: |IC| non-increasing as horizon grows.
        concrete = [(h, v) for h, v in zip(HORIZONS, ics, strict=False) if v is not None]
        monotonic = True
        for prev, curr in zip(concrete, concrete[1:], strict=False):
            if abs(curr[1]) > abs(prev[1]) + 0.02:  # small tolerance
                monotonic = False
                break

        results.append(
            {
                "factor": name,
                "ic": horizon_ic,
                "n": horizon_n,
                "monotonic_decay": monotonic,
            }
        )

    # Sort by best short-horizon IC.
    def _sort_key(entry: dict[str, Any]) -> float:
        v = entry["ic"].get("1d")
        return -abs(v) if v is not None else 0.0

    results.sort(key=_sort_key)
    return {
        "status": "ok",
        "sample_sizes": {f"{h}d": len(per_horizon[h]) for h in HORIZONS},
        "factors": results,
    }


def compute_rolling_ic(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    window_days: int = ROLLING_WINDOW_DAYS,
    step_days: int = ROLLING_STEP_DAYS,
) -> dict[str, Any]:
    """Rolling-window Spearman IC per factor — detects factor fatigue.

    Window anchored on the most recent signal_date and stepped backward.
    Each window emits one IC value per factor with enough rows.
    """
    observations = _evaluated_rows(rows, horizon)
    if len(observations) < MIN_SAMPLE_SIZE:
        return {
            "status": "insufficient_data",
            "sample_size": len(observations),
            "factors": [],
        }

    anchor = max(signal_date for signal_date, _, _ in observations)
    earliest = min(signal_date for signal_date, _, _ in observations)

    # Build windows [anchor - k*step - window, anchor - k*step).
    windows: list[tuple[date, date]] = []
    cursor_end = anchor + timedelta(days=1)
    while True:
        cursor_start = cursor_end - timedelta(days=window_days)
        windows.append((cursor_start, cursor_end))
        cursor_end = cursor_end - timedelta(days=step_days)
        if cursor_end <= earliest:
            break

    factor_names: set[str] = set()
    for _, factors, _ in observations:
        factor_names.update(factors.keys())

    factor_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for win_start, win_end in windows:
        window_obs = [o for o in observations if win_start <= o[0] < win_end]
        if len(window_obs) < MIN_ROWS_PER_WINDOW:
            continue
        for name in factor_names:
            xs: list[float] = []
            ys: list[float] = []
            for _, factors, ret in window_obs:
                if name in factors:
                    xs.append(factors[name])
                    ys.append(ret)
            if len(xs) < MIN_ROWS_PER_WINDOW:
                continue
            ic = _spearman(xs, ys)
            if ic is None:
                continue
            factor_series[name].append(
                {
                    "window_end": win_end.isoformat(),
                    "ic": round(ic, 3),
                    "n": len(xs),
                }
            )

    # Sort each factor's series chronologically.
    results: list[dict[str, Any]] = []
    for name, series in factor_series.items():
        if not series:
            continue
        series.sort(key=lambda p: p["window_end"])
        latest = series[-1]["ic"]
        lifetime = [p["ic"] for p in series]
        lifetime_avg = sum(lifetime) / len(lifetime)
        fatigue = latest < lifetime_avg - 0.1
        results.append(
            {
                "factor": name,
                "series": series,
                "latest_ic": latest,
                "lifetime_avg_ic": round(lifetime_avg, 3),
                "fatigue": fatigue,
            }
        )

    results.sort(key=lambda r: r["latest_ic"])
    return {
        "status": "ok",
        "sample_size": len(observations),
        "horizon": horizon,
        "window_days": window_days,
        "step_days": step_days,
        "factors": results,
    }


def compute_kelly_fractions(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> dict[str, Any]:
    """Per-direction Kelly fraction from hit rate × payoff.

    Formula: f* = p - (1 - p) / b, where
      - p = hit rate (win probability)
      - b = avg win / avg loss (payoff ratio)

    Returned fraction is half-Kelly (standard haircut for estimation noise).
    """
    rows_list = list(rows)
    per_direction: dict[str, list[float]] = defaultdict(list)
    for row in rows_list:
        if str(row.get(f"evaluated_{horizon}d", "False")).lower() != "true":
            continue
        direction = str(row.get("signal_direction", "neutral")).strip() or "neutral"
        ret = _parse_float(row.get(f"return_{horizon}d"))
        if ret is None:
            continue
        per_direction[direction].append(ret)

    results: dict[str, dict[str, Any]] = {}
    for direction, returns in per_direction.items():
        if len(returns) < MIN_ROWS_FOR_KELLY:
            results[direction] = {
                "status": "insufficient_data",
                "n": len(returns),
            }
            continue
        # "Win" direction-aware: bull wins on +return, bear wins on -return,
        # neutral wins on |ret|<=1.0 (matches signal_tracker._is_signal_win).
        if direction == "bull":
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r <= 0]
        elif direction == "bear":
            wins = [-r for r in returns if r < 0]
            losses = [-r for r in returns if r >= 0]
        else:
            wins = [r for r in returns if abs(r) <= 1.0]
            losses = [r for r in returns if abs(r) > 1.0]

        n = len(returns)
        p = len(wins) / n if n else 0.0
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

        if avg_loss <= 0 or p <= 0:
            kelly = 0.0
        else:
            b = avg_win / avg_loss if avg_loss else 0.0
            kelly = p - (1 - p) / b if b > 0 else 0.0

        kelly_clipped = max(0.0, min(1.0, kelly))
        results[direction] = {
            "status": "ok",
            "n": n,
            "hit_rate": round(p, 3),
            "avg_win": round(avg_win, 3),
            "avg_loss": round(avg_loss, 3),
            "payoff_ratio": round(avg_win / avg_loss, 3) if avg_loss else None,
            "kelly_full": round(kelly_clipped, 3),
            "kelly_half": round(kelly_clipped * KELLY_HAIRCUT, 3),
        }

    return {
        "status": "ok" if results else "insufficient_data",
        "horizon": horizon,
        "haircut": KELLY_HAIRCUT,
        "by_direction": results,
    }


def compute_signal_turnover(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    """Day-over-day Jaccard change of the active signal ticker set.

    1.0 = total churn (no overlap), 0.0 = identical set. Chronic extreme
    values hint at either whipsaw (too high) or staleness (too low).
    """
    by_date: dict[date, set[str]] = defaultdict(set)
    for row in rows:
        signal_date = _parse_iso_date(row.get("signal_date"))
        ticker = str(row.get("ticker", "")).strip().upper()
        if signal_date is None or not ticker:
            continue
        by_date[signal_date].add(ticker)

    if len(by_date) < 2:
        return {
            "status": "insufficient_data",
            "sample_size": len(by_date),
            "points": [],
        }

    sorted_dates = sorted(by_date.keys())
    points: list[dict[str, Any]] = []
    previous: set[str] | None = None
    for d in sorted_dates:
        current = by_date[d]
        if previous is not None:
            union = previous | current
            intersection = previous & current
            jaccard_change = (
                1.0 - (len(intersection) / len(union)) if union else 0.0
            )
            points.append(
                {
                    "date": d.isoformat(),
                    "tickers": len(current),
                    "turnover": round(jaccard_change, 3),
                }
            )
        previous = current

    if not points:
        return {"status": "insufficient_data", "sample_size": len(by_date), "points": []}
    avg_turnover = sum(p["turnover"] for p in points) / len(points)
    return {
        "status": "ok",
        "sample_size": len(by_date),
        "avg_turnover": round(avg_turnover, 3),
        "points": points,
    }


def build_signal_quality_payload(
    rows: Iterable[dict[str, str]],
) -> dict[str, Any]:
    """Single entry point for the dashboard IC panel."""
    rows_list = list(rows)
    return {
        "ic_decay": compute_ic_decay(rows_list),
        "rolling_ic": compute_rolling_ic(rows_list, horizon=5),
        "kelly": compute_kelly_fractions(rows_list, horizon=5),
        "turnover": compute_signal_turnover(rows_list),
    }
