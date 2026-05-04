from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from src.decision.action_change_reason import build_action_change_reasons
from src.output.schema import SCHEMA_VERSION
from src.types import MarketRegime, TickerDecision
from src.utils.performance_analytics import (
    build_conviction_calibration,
    build_factor_attribution,
    build_regime_performance,
    build_signal_performance,
)
from src.utils.signal_tracker import load_signal_rows


def write_analysis_performance_output(
    *,
    output_root: Path | None = None,
    run_date: date,
    decisions: list[TickerDecision],
    market_regime: MarketRegime,
    signal_rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    root = output_root or Path("output")
    rows = signal_rows
    if rows is None:
        rows = load_signal_rows(root / "data" / "signal_tracker.csv")

    payload = build_analysis_performance_payload(
        rows,
        run_date=run_date,
        decisions=decisions,
        market_regime=market_regime,
    )

    path = root / "data" / "analysis_performance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_web_public_analysis_performance(path, root.parent)
    return payload


def build_analysis_performance_payload(
    signal_rows: list[dict[str, str]],
    *,
    run_date: date,
    decisions: list[TickerDecision],
    market_regime: MarketRegime,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": run_date.isoformat(),
        "summary": {
            "sample_count": len(signal_rows),
            "decision_count": len(decisions),
            "completed_return_windows": _completed_return_windows(signal_rows),
            "mode": "shadow_observational",
            "notes": [
                "Analytics are observational shadow metrics and do not recompute or mutate official decisions.",
                "Factor attribution shows observed associations only and is not causal.",
            ],
        },
        "signal_performance": build_signal_performance(signal_rows),
        "conviction_calibration": build_conviction_calibration(signal_rows),
        "regime_performance": build_regime_performance(signal_rows),
        "factor_attribution": build_factor_attribution(signal_rows),
        "action_change_reasons": build_action_change_reasons(
            decisions,
            signal_rows,
            run_date=run_date,
            market_regime=market_regime,
        ),
    }


def _completed_return_windows(signal_rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        f"{horizon}d": sum(1 for row in signal_rows if _is_completed(row.get(f"evaluated_{horizon}d")))
        for horizon in (1, 5, 20)
    }


def _is_completed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def _sync_web_public_analysis_performance(source_path: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists() or not source_path.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_dir / source_path.name)
