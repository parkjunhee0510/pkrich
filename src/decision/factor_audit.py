"""Factor health audit.

Uses persisted per-signal factor scores (stored in `factors_json` on each
`signal_tracker.csv` row) plus realized forward returns to surface three
health signals for the decision layer:

1. **Collinearity** — Pearson ρ between factor pairs. |ρ|>0.6 means the two
   factors are likely redundant and should be merged or down-weighted.
2. **Information ratio (IR)** — Spearman rank correlation between a factor's
   score and the realized 5D return. |IR|<0.1 indicates the factor adds
   little predictive value and is a candidate for removal.
3. **Weak factor list** — factors flagged by #2 that should be reviewed.

The module is defensive about missing data — when row count is low, results
are returned with `status: "insufficient_data"` so the Admin UI can render a
helpful message instead of an empty table.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Iterable

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")

COLLINEARITY_THRESHOLD = 0.6
WEAK_FACTOR_IR_THRESHOLD = 0.1
MIN_SAMPLE_SIZE = 10
# Weight-decay suggestions need more samples than raw IR: a |IR|<0.1 verdict
# on 10 rows is noise, not signal. 50 matches Phase 2 gating in the roadmap.
MIN_SAMPLE_FOR_DECAY = 50
DECAY_FACTOR = 0.5


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


def _parse_factors(raw: object) -> dict[str, float]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in decoded.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _extract_factor_rows(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> list[tuple[dict[str, float], float]]:
    """Return (factors, realized_return) pairs for evaluated rows only."""
    usable: list[tuple[dict[str, float], float]] = []
    for row in rows:
        if str(row.get(f"evaluated_{horizon}d", "False")).lower() != "true":
            continue
        factors = _parse_factors(row.get("factors_json"))
        if not factors:
            continue
        ret = _parse_float(row.get(f"return_{horizon}d"))
        if ret is None:
            continue
        usable.append((factors, ret))
    return usable


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = _mean(xs)
    my = _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    denom_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return None
    return num / (denom_x * denom_y)


def _rank(values: list[float]) -> list[float]:
    """Average-rank values (1-indexed) with ties resolved by mean rank."""
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return _pearson(_rank(xs), _rank(ys))


def compute_factor_correlations(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> dict[str, Any]:
    """Pairwise Pearson ρ for every factor that appears together in ≥MIN_SAMPLE
    rows. Reports pairs sorted by |ρ| descending with a collinear flag."""
    pairs_data = _extract_factor_rows(rows, horizon=horizon)
    if len(pairs_data) < MIN_SAMPLE_SIZE:
        return {
            "status": "insufficient_data",
            "sample_size": len(pairs_data),
            "pairs": [],
            "threshold": COLLINEARITY_THRESHOLD,
        }

    # Collect factor columns
    factor_values: dict[str, list[float]] = {}
    for factors, _ in pairs_data:
        for name, value in factors.items():
            factor_values.setdefault(name, []).append(value)

    # Only keep factors seen in most rows
    full_n = len(pairs_data)
    candidate_factors = [name for name, values in factor_values.items() if len(values) >= MIN_SAMPLE_SIZE]
    # Rebuild aligned vectors — only use rows where BOTH factors are present.
    pair_results: list[dict[str, Any]] = []
    for i, name_a in enumerate(candidate_factors):
        for name_b in candidate_factors[i + 1:]:
            xs: list[float] = []
            ys: list[float] = []
            for factors, _ in pairs_data:
                if name_a in factors and name_b in factors:
                    xs.append(factors[name_a])
                    ys.append(factors[name_b])
            if len(xs) < MIN_SAMPLE_SIZE:
                continue
            rho = _pearson(xs, ys)
            if rho is None:
                continue
            pair_results.append({
                "factor_a": name_a,
                "factor_b": name_b,
                "rho": round(rho, 3),
                "n": len(xs),
                "collinear": abs(rho) >= COLLINEARITY_THRESHOLD,
            })

    pair_results.sort(key=lambda r: abs(r["rho"]), reverse=True)
    return {
        "status": "ok",
        "sample_size": full_n,
        "horizon": horizon,
        "threshold": COLLINEARITY_THRESHOLD,
        "pairs": pair_results,
        "collinear_pairs": [p for p in pair_results if p["collinear"]],
    }


def compute_factor_ir(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> dict[str, Any]:
    """Per-factor Spearman rank correlation with realized return. Factors with
    |IR| < WEAK_FACTOR_IR_THRESHOLD are flagged as weak."""
    pairs_data = _extract_factor_rows(rows, horizon=horizon)
    if len(pairs_data) < MIN_SAMPLE_SIZE:
        return {
            "status": "insufficient_data",
            "sample_size": len(pairs_data),
            "factors": [],
            "weak_factors": [],
            "threshold": WEAK_FACTOR_IR_THRESHOLD,
        }

    factor_names: set[str] = set()
    for factors, _ in pairs_data:
        factor_names.update(factors.keys())

    factor_rows: list[dict[str, Any]] = []
    for name in sorted(factor_names):
        xs: list[float] = []
        ys: list[float] = []
        for factors, ret in pairs_data:
            if name in factors:
                xs.append(factors[name])
                ys.append(ret)
        if len(xs) < MIN_SAMPLE_SIZE:
            continue
        ir = _spearman(xs, ys)
        if ir is None:
            continue
        mean_when_positive = _mean([r for x, r in zip(xs, ys, strict=False) if x > 0])
        mean_when_negative = _mean([r for x, r in zip(xs, ys, strict=False) if x < 0])
        factor_rows.append({
            "factor": name,
            "ir": round(ir, 3),
            "n": len(xs),
            "mean_return_when_positive": round(mean_when_positive, 3),
            "mean_return_when_negative": round(mean_when_negative, 3),
            "weak": abs(ir) < WEAK_FACTOR_IR_THRESHOLD,
        })

    factor_rows.sort(key=lambda r: abs(r["ir"]), reverse=True)
    return {
        "status": "ok",
        "sample_size": len(pairs_data),
        "horizon": horizon,
        "threshold": WEAK_FACTOR_IR_THRESHOLD,
        "factors": factor_rows,
        "weak_factors": [r["factor"] for r in factor_rows if r["weak"]],
    }


def suggest_weight_decays(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
    current_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Propose halving `weight_range` (min/max) for factors with |IR| < 0.1.

    Preconditions:
      - Per-factor sample size ≥ MIN_SAMPLE_FOR_DECAY. Below this the IR
        sign/magnitude is noise; we refuse to recommend decay.
      - Operator applies decisions manually in `config/decision_weights.yaml`.
        This function never writes — it only produces the diff to review.

    Halving semantics: both `min` (if negative) and `max` scale toward zero
    by DECAY_FACTOR. A factor with only `max` keeps the floor at 0.
    """
    rows_list = list(rows)
    ir_report = compute_factor_ir(rows_list, horizon=horizon)

    if ir_report["status"] != "ok":
        return {
            "status": "insufficient_data",
            "horizon": horizon,
            "sample_size": ir_report.get("sample_size", 0),
            "min_required_per_factor": MIN_SAMPLE_FOR_DECAY,
            "suggestions": [],
        }

    current_factors: dict[str, dict[str, float]] = {}
    if current_config is not None:
        raw = current_config.get("factors", {}) if isinstance(current_config, dict) else {}
        for name, spec in raw.items():
            if isinstance(spec, dict):
                current_factors[name] = {
                    "min": float(spec.get("min", 0.0)),
                    "max": float(spec.get("max", 0.0)),
                }

    suggestions: list[dict[str, Any]] = []
    for factor_row in ir_report["factors"]:
        if not factor_row["weak"]:
            continue
        if factor_row["n"] < MIN_SAMPLE_FOR_DECAY:
            continue
        name = factor_row["factor"]
        current = current_factors.get(name)
        if current is None:
            continue
        suggested_min = round(current["min"] * DECAY_FACTOR, 2)
        suggested_max = round(current["max"] * DECAY_FACTOR, 2)
        suggestions.append({
            "factor": name,
            "ir": factor_row["ir"],
            "n": factor_row["n"],
            "current": {"min": current["min"], "max": current["max"]},
            "suggested": {"min": suggested_min, "max": suggested_max},
            "reason": f"|IR|={abs(factor_row['ir']):.3f} < {WEAK_FACTOR_IR_THRESHOLD}",
        })

    return {
        "status": "ok",
        "horizon": horizon,
        "sample_size": ir_report["sample_size"],
        "min_required_per_factor": MIN_SAMPLE_FOR_DECAY,
        "decay_factor": DECAY_FACTOR,
        "suggestions": suggestions,
    }


def _load_decision_weights_config() -> dict[str, Any]:
    """Read `config/decision_weights.yaml` defensively — missing file → {}."""
    from pathlib import Path
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}
    path = Path("config/decision_weights.yaml")
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def build_factor_audit_payload(
    rows: Iterable[dict[str, str]],
    *,
    horizon: int = 5,
) -> dict[str, Any]:
    rows_list = list(rows)
    config = _load_decision_weights_config()
    return {
        "horizon": horizon,
        "collinearity": compute_factor_correlations(rows_list, horizon=horizon),
        "factor_ir": compute_factor_ir(rows_list, horizon=horizon),
        "weight_decays": suggest_weight_decays(
            rows_list, horizon=horizon, current_config=config
        ),
    }
