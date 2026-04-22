"""Regime-multiplier grid search and threshold refit.

Step 6 of the conviction-quality roadmap: close the outer loop by letting
the signal ledger choose weights instead of hand-tuning them.

Two entry points:

- `grid_search_regime_multipliers(rows)` — enumerate 3^5 regime-multiplier
  combinations per regime, score each by Spearman(conviction_hat, return_5d)
  on the subset of rows for that regime, return the argmax plus a short
  candidate leaderboard. Uses the per-row `factors_json` snapshot so the
  search is counterfactual-safe (no refitting against future factor scores).
- `suggest_thresholds(rows)` — empirical quantiles of realized conviction
  to replace the hardcoded buy=65 / avoid=35 cutoffs in
  `config/decision_weights.yaml`. Bottom/top terciles by conviction → avoid
  / buy bands; risk_off gets its own quantile so the regime can run hotter.

Runtime fit only — does not write config automatically. Designed to be
invoked from an offline script (not the daily pipeline) once signal volume
is sufficient. Guard rails:
  - `MIN_SAMPLES_PER_REGIME=30` — below this, grid search returns
    `status: "insufficient_data"`.
  - Gradient descent is intentionally deferred until ≥500 signals (the
    search space is small enough that brute force is honest).
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Iterable

from src.decision.factor_audit import _parse_factors, _parse_float, _spearman

# 5 factors chosen because they dominate the weighted sum in practice:
# momentum / valuation / signal_track_record / catalyst_recency / news_tone.
# Tuning regime_adjustment itself would double-count regime (the regime
# signal is already in the multiplier dimension).
TUNABLE_FACTORS: tuple[str, ...] = (
    "momentum",
    "valuation",
    "signal_track_record",
    "catalyst_recency",
    "news_tone",
)

# Three-level grid per factor. 3^5 = 243 combinations per regime.
MULTIPLIER_GRID: tuple[float, ...] = (0.7, 1.0, 1.3)

MIN_SAMPLES_PER_REGIME = 30
MIN_SAMPLES_FOR_THRESHOLDS = 50

# Walk-forward CV: honest out-of-sample evaluation. Without this, the grid
# search's in-sample Spearman silently overfits — every tuning decision
# downstream (Phase 2+) leans on this number being trustworthy.
WALKFORWARD_DEFAULT_FOLDS = 5
WALKFORWARD_MIN_TEST_SIZE = 10
WALKFORWARD_MIN_TRAIN_SIZE = 20

# Purged K-fold + embargo (López de Prado, Advances in Financial ML, ch.7).
# Labels are computed as forward N-day returns, so a training sample whose
# label window overlaps the test window leaks the test label back into
# training. `PURGE_HORIZON_DEFAULT` must match the return horizon used for
# the label. `EMBARGO_DAYS` adds a one-sided gap after the test window to
# absorb residual autocorrelation in the error term.
PURGE_HORIZON_DEFAULT = 5
EMBARGO_DAYS_DEFAULT = 5


def _weighted_sum(factors: dict[str, float], multipliers: dict[str, float]) -> float:
    """Pure weighted sum — no regime normalization needed for Spearman."""
    total = 0.0
    for name, value in factors.items():
        total += value * multipliers.get(name, 1.0)
    return total


def _iter_grid() -> Iterable[dict[str, float]]:
    """Yield every multiplier combination over TUNABLE_FACTORS × MULTIPLIER_GRID."""
    grid = MULTIPLIER_GRID
    factors = TUNABLE_FACTORS
    # Manual 5-deep product to avoid itertools import churn; explicit is fine.
    for a in grid:
        for b in grid:
            for c in grid:
                for d in grid:
                    for e in grid:
                        yield {
                            factors[0]: a,
                            factors[1]: b,
                            factors[2]: c,
                            factors[3]: d,
                            factors[4]: e,
                        }


def _extract_regime_rows(
    rows: Iterable[dict[str, str]],
    regime: str,
    *,
    horizon: int = 5,
) -> list[tuple[dict[str, float], float]]:
    """(factors_json, return) pairs for evaluated rows matching `regime`."""
    want_regime = regime.strip().lower()
    usable: list[tuple[dict[str, float], float]] = []
    for row in rows:
        if str(row.get(f"evaluated_{horizon}d", "False")).lower() != "true":
            continue
        row_regime = str(row.get("regime", "")).strip().lower()
        if row_regime != want_regime:
            continue
        factors = _parse_factors(row.get("factors_json"))
        if not factors:
            continue
        ret = _parse_float(row.get(f"return_{horizon}d"))
        if ret is None:
            continue
        usable.append((factors, ret))
    return usable


def grid_search_regime_multipliers(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    top_k: int = 5,
) -> dict[str, Any]:
    """Per-regime grid search over TUNABLE_FACTORS × MULTIPLIER_GRID.

    Objective: maximize Spearman(weighted_sum, return_{horizon}d). Spearman
    is scale-invariant so we skip the conviction 0-100 normalization step
    entirely (the rank ordering is what matters).

    Returns: {
        status, horizon,
        regimes: {
            risk_on: {
                sample_size, best: {multipliers, spearman},
                candidates: [top_k {multipliers, spearman}],
            }, ...
        }
    }
    """
    rows_list = list(rows)
    report: dict[str, Any] = {
        "status": "ok",
        "horizon": horizon,
        "tunable_factors": list(TUNABLE_FACTORS),
        "grid": list(MULTIPLIER_GRID),
        "regimes": {},
    }

    for regime in ("risk_on", "risk_off", "neutral", "reflation", "defensive_bias"):
        data = _extract_regime_rows(rows_list, regime, horizon=horizon)
        if len(data) < MIN_SAMPLES_PER_REGIME:
            report["regimes"][regime] = {
                "status": "insufficient_data",
                "sample_size": len(data),
                "min_required": MIN_SAMPLES_PER_REGIME,
                "best": None,
                "candidates": [],
            }
            continue

        realized = [ret for _, ret in data]
        scored: list[tuple[float, dict[str, float]]] = []
        for multipliers in _iter_grid():
            predicted = [_weighted_sum(factors, multipliers) for factors, _ in data]
            rho = _spearman(predicted, realized)
            if rho is None or math.isnan(rho):
                continue
            scored.append((rho, multipliers))

        if not scored:
            report["regimes"][regime] = {
                "status": "insufficient_data",
                "sample_size": len(data),
                "best": None,
                "candidates": [],
            }
            continue

        scored.sort(key=lambda pair: pair[0], reverse=True)
        best_rho, best_multipliers = scored[0]
        report["regimes"][regime] = {
            "status": "ok",
            "sample_size": len(data),
            "best": {
                "multipliers": {k: round(v, 2) for k, v in best_multipliers.items()},
                "spearman": round(best_rho, 4),
            },
            "candidates": [
                {
                    "multipliers": {k: round(v, 2) for k, v in mults.items()},
                    "spearman": round(rho, 4),
                }
                for rho, mults in scored[:top_k]
            ],
        }

    return report


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolation quantile (NumPy default)."""
    if not values:
        raise ValueError("empty values")
    sorted_values = sorted(values)
    pos = (len(sorted_values) - 1) * q
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return sorted_values[lower]
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def suggest_thresholds(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> dict[str, Any]:
    """Empirical conviction quantiles per regime.

    Strategy:
      - buy = 70th percentile of conviction among EVALUATED rows
      - avoid = 30th percentile of conviction among EVALUATED rows
      - buy_risk_off = 70th percentile within risk_off rows (falls back to
        +10 over buy if the regime's own sample is thin)

    This replaces `decision_weights.yaml` hardcoded thresholds (65/75/35)
    with the distributional cutoffs actually observed in production. The
    intent is to keep the action mix roughly stable across regimes — the
    current 65 cutoff produces very different hit rates in risk_on vs
    risk_off, because the weighted sum rescales with multipliers.
    """
    rows_list = list(rows)
    convictions_all: list[float] = []
    convictions_risk_off: list[float] = []

    for row in rows_list:
        if str(row.get(f"evaluated_{horizon}d", "False")).lower() != "true":
            continue
        conviction = _parse_float(row.get("conviction"))
        if conviction is None:
            continue
        convictions_all.append(conviction)
        if str(row.get("regime", "")).strip().lower() == "risk_off":
            convictions_risk_off.append(conviction)

    if len(convictions_all) < MIN_SAMPLES_FOR_THRESHOLDS:
        return {
            "status": "insufficient_data",
            "sample_size": len(convictions_all),
            "min_required": MIN_SAMPLES_FOR_THRESHOLDS,
            "horizon": horizon,
        }

    buy = _quantile(convictions_all, 0.70)
    avoid = _quantile(convictions_all, 0.30)
    if len(convictions_risk_off) >= MIN_SAMPLES_FOR_THRESHOLDS // 2:
        buy_risk_off = _quantile(convictions_risk_off, 0.70)
    else:
        buy_risk_off = min(100.0, buy + 10.0)

    return {
        "status": "ok",
        "horizon": horizon,
        "sample_size": len(convictions_all),
        "sample_size_risk_off": len(convictions_risk_off),
        "suggested": {
            "buy": int(round(buy)),
            "buy_risk_off": int(round(buy_risk_off)),
            "avoid": int(round(avoid)),
        },
    }


def _extract_regime_rows_dated(
    rows: Iterable[dict[str, str]],
    regime: str,
    *,
    horizon: int = 5,
) -> list[tuple[str, dict[str, float], float]]:
    """Like `_extract_regime_rows` but preserves `signal_date` for ordering."""
    want_regime = regime.strip().lower()
    usable: list[tuple[str, dict[str, float], float]] = []
    for row in rows:
        if str(row.get(f"evaluated_{horizon}d", "False")).lower() != "true":
            continue
        if str(row.get("regime", "")).strip().lower() != want_regime:
            continue
        factors = _parse_factors(row.get("factors_json"))
        if not factors:
            continue
        ret = _parse_float(row.get(f"return_{horizon}d"))
        if ret is None:
            continue
        signal_date = str(row.get("signal_date", "")).strip()
        if not signal_date:
            continue
        usable.append((signal_date, factors, ret))
    return usable


def _best_multipliers_on(
    data: list[tuple[dict[str, float], float]],
) -> tuple[dict[str, float] | None, float | None]:
    """Grid search on an arbitrary (factors, return) slice. Returns best (mults, rho)."""
    realized = [ret for _, ret in data]
    best_rho: float | None = None
    best_mults: dict[str, float] | None = None
    for multipliers in _iter_grid():
        predicted = [_weighted_sum(factors, multipliers) for factors, _ in data]
        rho = _spearman(predicted, realized)
        if rho is None or math.isnan(rho):
            continue
        if best_rho is None or rho > best_rho:
            best_rho = rho
            best_mults = multipliers
    return best_mults, best_rho


def walk_forward_grid_search(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    n_folds: int = WALKFORWARD_DEFAULT_FOLDS,
) -> dict[str, Any]:
    """Expanding-window walk-forward CV for regime multiplier grid search.

    For each regime:
      1. Sort evaluated rows by signal_date.
      2. Partition the tail into `n_folds` contiguous test windows; train
         set for fold k is all rows strictly preceding that window.
      3. Fit best multipliers on train via grid search, then score them on
         the held-out test window via Spearman.
      4. Report per-fold OOS ρ, the mean/std across folds, and the full-set
         in-sample ρ for comparison. Large IS-OOS gap ⇒ overfit warning.

    Guard rails: skip folds with train < `WALKFORWARD_MIN_TRAIN_SIZE` or
    test < `WALKFORWARD_MIN_TEST_SIZE`; if fewer than 2 valid folds remain,
    report `insufficient_data` for that regime.
    """
    rows_list = list(rows)
    report: dict[str, Any] = {
        "status": "ok",
        "horizon": horizon,
        "n_folds_requested": n_folds,
        "regimes": {},
    }

    for regime in ("risk_on", "risk_off", "neutral", "reflation", "defensive_bias"):
        dated = _extract_regime_rows_dated(rows_list, regime, horizon=horizon)
        dated.sort(key=lambda triple: triple[0])
        total = len(dated)

        min_total = WALKFORWARD_MIN_TRAIN_SIZE + 2 * WALKFORWARD_MIN_TEST_SIZE
        if total < min_total:
            report["regimes"][regime] = {
                "status": "insufficient_data",
                "sample_size": total,
                "min_required": min_total,
                "folds": [],
                "oos_spearman_mean": None,
                "oos_spearman_std": None,
                "in_sample_spearman": None,
                "selected_multipliers": None,
            }
            continue

        # Carve the last ~60% into `n_folds` sequential test windows so the
        # first fold still has a reasonably large training prefix.
        test_region_start = max(WALKFORWARD_MIN_TRAIN_SIZE, total // 3)
        test_pool = total - test_region_start
        fold_size = max(WALKFORWARD_MIN_TEST_SIZE, test_pool // n_folds)

        fold_results: list[dict[str, Any]] = []
        oos_rhos: list[float] = []
        cursor = test_region_start
        while cursor < total and len(fold_results) < n_folds:
            test_end = min(cursor + fold_size, total)
            train_slice = [(f, r) for _, f, r in dated[:cursor]]
            test_slice = [(f, r) for _, f, r in dated[cursor:test_end]]
            cursor = test_end

            if len(train_slice) < WALKFORWARD_MIN_TRAIN_SIZE:
                continue
            if len(test_slice) < WALKFORWARD_MIN_TEST_SIZE:
                continue

            train_mults, train_rho = _best_multipliers_on(train_slice)
            if train_mults is None:
                continue

            predicted_test = [_weighted_sum(f, train_mults) for f, _ in test_slice]
            realized_test = [r for _, r in test_slice]
            oos_rho = _spearman(predicted_test, realized_test)
            if oos_rho is None or math.isnan(oos_rho):
                continue

            fold_results.append({
                "train_size": len(train_slice),
                "test_size": len(test_slice),
                "train_spearman": round(train_rho, 4) if train_rho is not None else None,
                "oos_spearman": round(oos_rho, 4),
                "multipliers": {k: round(v, 2) for k, v in train_mults.items()},
            })
            oos_rhos.append(oos_rho)

        if len(fold_results) < 2:
            report["regimes"][regime] = {
                "status": "insufficient_data",
                "sample_size": total,
                "folds": fold_results,
                "oos_spearman_mean": None,
                "oos_spearman_std": None,
                "in_sample_spearman": None,
                "selected_multipliers": None,
            }
            continue

        mean_rho = sum(oos_rhos) / len(oos_rhos)
        variance = sum((r - mean_rho) ** 2 for r in oos_rhos) / len(oos_rhos)
        std_rho = math.sqrt(variance)

        full = [(f, r) for _, f, r in dated]
        full_mults, full_rho = _best_multipliers_on(full)

        report["regimes"][regime] = {
            "status": "ok",
            "sample_size": total,
            "folds": fold_results,
            "oos_spearman_mean": round(mean_rho, 4),
            "oos_spearman_std": round(std_rho, 4),
            "in_sample_spearman": round(full_rho, 4) if full_rho is not None else None,
            "overfit_gap": (
                round(full_rho - mean_rho, 4)
                if full_rho is not None
                else None
            ),
            "selected_multipliers": (
                {k: round(v, 2) for k, v in full_mults.items()}
                if full_mults is not None
                else None
            ),
        }

    return report


def _parse_iso_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw.strip())
    except (ValueError, AttributeError):
        return None


def _purge_training_set(
    dated: list[tuple[str, dict[str, float], float]],
    test_start: date,
    test_end: date,
    *,
    horizon_days: int,
    embargo_days: int,
) -> list[tuple[dict[str, float], float]]:
    """Drop training samples whose label window overlaps the test window
    (after adding `embargo_days` of one-sided padding on each side).

    Label window for a sample observed on `d` is `[d, d + horizon_days]` —
    if any part of that interval falls within `[test_start - embargo,
    test_end + embargo]`, the sample is purged.
    """
    embargo_start = test_start - timedelta(days=embargo_days)
    embargo_end = test_end + timedelta(days=embargo_days)
    keep: list[tuple[dict[str, float], float]] = []
    for signal_date_str, factors, ret in dated:
        signal_date = _parse_iso_date(signal_date_str)
        if signal_date is None:
            continue
        label_start = signal_date
        label_end = signal_date + timedelta(days=horizon_days)
        # Overlap check: two intervals overlap iff start_a <= end_b and
        # start_b <= end_a.
        overlaps = label_start <= embargo_end and embargo_start <= label_end
        if overlaps:
            continue
        keep.append((factors, ret))
    return keep


def purged_walk_forward_grid_search(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    n_folds: int = WALKFORWARD_DEFAULT_FOLDS,
    embargo_days: int = EMBARGO_DAYS_DEFAULT,
    purge_horizon_days: int | None = None,
) -> dict[str, Any]:
    """Walk-forward grid search with purging + embargo (López de Prado).

    The plain `walk_forward_grid_search` partitions by row index, which
    silently leaks labels: a train row at position (cursor - 1) has its
    forward 5D return bleeding into the first few days of the test fold.
    Purging drops any train row whose `[signal_date, signal_date + horizon]`
    window touches the embargoed test window; embargo pads both sides so
    residual autocorrelation in the error term can't sneak across either.

    Each fold reports its in-sample ρ (on the purged train set) and OOS
    ρ (on the untouched test set). The gap between the two is the honest
    overfit estimate — substantially more trustworthy than the naive
    walk-forward's, which inherits a leaked baseline.
    """
    rows_list = list(rows)
    horizon_days = purge_horizon_days if purge_horizon_days is not None else horizon
    report: dict[str, Any] = {
        "status": "ok",
        "horizon": horizon,
        "n_folds_requested": n_folds,
        "embargo_days": embargo_days,
        "purge_horizon_days": horizon_days,
        "regimes": {},
    }

    for regime in ("risk_on", "risk_off", "neutral", "reflation", "defensive_bias"):
        dated = _extract_regime_rows_dated(rows_list, regime, horizon=horizon)
        dated.sort(key=lambda triple: triple[0])
        total = len(dated)

        min_total = WALKFORWARD_MIN_TRAIN_SIZE + 2 * WALKFORWARD_MIN_TEST_SIZE
        if total < min_total:
            report["regimes"][regime] = {
                "status": "insufficient_data",
                "sample_size": total,
                "min_required": min_total,
                "folds": [],
                "oos_spearman_mean": None,
                "oos_spearman_std": None,
                "selected_multipliers": None,
            }
            continue

        test_region_start = max(WALKFORWARD_MIN_TRAIN_SIZE, total // 3)
        test_pool = total - test_region_start
        fold_size = max(WALKFORWARD_MIN_TEST_SIZE, test_pool // n_folds)

        fold_results: list[dict[str, Any]] = []
        oos_rhos: list[float] = []
        purged_counts: list[int] = []
        cursor = test_region_start
        while cursor < total and len(fold_results) < n_folds:
            test_end_idx = min(cursor + fold_size, total)
            test_window = dated[cursor:test_end_idx]
            cursor = test_end_idx
            if len(test_window) < WALKFORWARD_MIN_TEST_SIZE:
                continue

            test_start_date = _parse_iso_date(test_window[0][0])
            test_end_date = _parse_iso_date(test_window[-1][0])
            if test_start_date is None or test_end_date is None:
                continue

            # Train candidates = everything NOT in the test window.
            raw_train = [d for d in dated if d not in test_window]
            train_slice = _purge_training_set(
                raw_train,
                test_start_date,
                test_end_date,
                horizon_days=horizon_days,
                embargo_days=embargo_days,
            )
            purged_count = len(raw_train) - len(train_slice)
            purged_counts.append(purged_count)

            if len(train_slice) < WALKFORWARD_MIN_TRAIN_SIZE:
                fold_results.append({
                    "status": "skipped_small_train",
                    "train_size": len(train_slice),
                    "purged": purged_count,
                    "test_size": len(test_window),
                    "test_start": test_start_date.isoformat(),
                    "test_end": test_end_date.isoformat(),
                })
                continue

            train_mults, train_rho = _best_multipliers_on(train_slice)
            if train_mults is None:
                continue

            test_pairs = [(f, r) for _, f, r in test_window]
            predicted_test = [_weighted_sum(f, train_mults) for f, _ in test_pairs]
            realized_test = [r for _, r in test_pairs]
            oos_rho = _spearman(predicted_test, realized_test)
            if oos_rho is None or math.isnan(oos_rho):
                continue

            fold_results.append({
                "status": "ok",
                "train_size": len(train_slice),
                "purged": purged_count,
                "test_size": len(test_window),
                "test_start": test_start_date.isoformat(),
                "test_end": test_end_date.isoformat(),
                "train_spearman": round(train_rho, 4) if train_rho is not None else None,
                "oos_spearman": round(oos_rho, 4),
                "multipliers": {k: round(v, 2) for k, v in train_mults.items()},
            })
            oos_rhos.append(oos_rho)

        valid_folds = [f for f in fold_results if f.get("status") == "ok"]
        if len(valid_folds) < 2:
            report["regimes"][regime] = {
                "status": "insufficient_data",
                "sample_size": total,
                "folds": fold_results,
                "oos_spearman_mean": None,
                "oos_spearman_std": None,
                "selected_multipliers": None,
                "avg_purged_per_fold": (
                    round(sum(purged_counts) / len(purged_counts), 1)
                    if purged_counts else None
                ),
            }
            continue

        mean_rho = sum(oos_rhos) / len(oos_rhos)
        variance = sum((r - mean_rho) ** 2 for r in oos_rhos) / len(oos_rhos)
        std_rho = math.sqrt(variance)

        # Full-set in-sample reference is purely informational — the
        # whole point of purging is to stop trusting it. Keep it but
        # label clearly.
        full = [(f, r) for _, f, r in dated]
        full_mults, full_rho = _best_multipliers_on(full)

        report["regimes"][regime] = {
            "status": "ok",
            "sample_size": total,
            "folds": fold_results,
            "oos_spearman_mean": round(mean_rho, 4),
            "oos_spearman_std": round(std_rho, 4),
            "in_sample_spearman_leaky": round(full_rho, 4) if full_rho is not None else None,
            "overfit_gap": (
                round(full_rho - mean_rho, 4) if full_rho is not None else None
            ),
            "avg_purged_per_fold": (
                round(sum(purged_counts) / len(purged_counts), 1)
                if purged_counts else 0.0
            ),
            "selected_multipliers": (
                {k: round(v, 2) for k, v in full_mults.items()}
                if full_mults is not None
                else None
            ),
        }

    return report


def build_tuning_payload(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    include_walk_forward: bool = True,
    include_purged_walk_forward: bool = True,
) -> dict[str, Any]:
    """Convenience wrapper returning grid search, walk-forward CV, and thresholds."""
    rows_list = list(rows)
    payload: dict[str, Any] = {
        "horizon": horizon,
        "regime_multipliers": grid_search_regime_multipliers(rows_list, horizon=horizon),
        "thresholds": suggest_thresholds(rows_list, horizon=horizon),
    }
    if include_walk_forward:
        payload["walk_forward"] = walk_forward_grid_search(rows_list, horizon=horizon)
    if include_purged_walk_forward:
        payload["purged_walk_forward"] = purged_walk_forward_grid_search(
            rows_list, horizon=horizon
        )
    return payload


def apply_tuned_multipliers_to_yaml(
    rows: Iterable[dict[str, str]],
    yaml_path: str = "config/decision_weights.yaml",
    *,
    horizon: int = 5,
    min_spearman: float = 0.05,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge grid-search winners back into ``decision_weights.yaml``.

    Conservative by design: only overwrites multipliers for a regime when the
    best Spearman ≥ ``min_spearman`` and the regime had ≥MIN_SAMPLES_PER_REGIME
    evaluated rows. Never touches regimes where data is insufficient, so this
    is safe to run as a scheduled calibration job.
    """
    try:
        import yaml  # type: ignore
    except Exception:
        return {"status": "pyyaml_missing"}

    report = grid_search_regime_multipliers(rows, horizon=horizon)
    summary: dict[str, Any] = {"status": "ok", "updated_regimes": [], "skipped": {}}

    from pathlib import Path

    path = Path(yaml_path)
    if not path.exists():
        return {"status": "yaml_missing", "path": str(path)}
    with path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    multipliers_block = config.setdefault("regime_multipliers", {})
    for regime, info in report.get("regimes", {}).items():
        if info.get("status") != "ok":
            summary["skipped"][regime] = info.get("status", "unknown")
            continue
        best = info.get("best") or {}
        rho = float(best.get("spearman") or 0.0)
        if rho < min_spearman:
            summary["skipped"][regime] = f"spearman_below_{min_spearman}"
            continue
        tuned = best.get("multipliers") or {}
        if not tuned:
            summary["skipped"][regime] = "no_multipliers"
            continue
        current = dict(multipliers_block.get(regime) or {})
        current.update({k: float(v) for k, v in tuned.items()})
        multipliers_block[regime] = current
        summary["updated_regimes"].append({
            "regime": regime,
            "spearman": rho,
            "multipliers": current,
        })

    if not dry_run and summary["updated_regimes"]:
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)
    summary["yaml_path"] = str(path)
    summary["dry_run"] = dry_run
    return summary
