"""Write shadow analysis performance analytics."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Any

from src.decision.action_change_reason import build_action_change_reasons
from src.output.json_writer import write_json_file
from src.output.schema import SCHEMA_VERSION
from src.types import MarketRegime, TickerDecision
from src.utils.performance_analytics import (
    build_ai_recommendation_backtest,
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
    data_dir = root / "data"
    rows = signal_rows if signal_rows is not None else load_signal_rows(data_dir / "signal_tracker.csv")
    payload = build_analysis_performance_payload(
        rows,
        run_date=run_date,
        decisions=decisions,
        market_regime=market_regime,
    )
    path = data_dir / "analysis_performance.json"
    write_json_file(path, payload)
    _sync_web_public(path, root.parent)
    return payload


def build_analysis_performance_payload(
    signal_rows: list[dict[str, str]],
    *,
    run_date: date,
    decisions: list[TickerDecision],
    market_regime: MarketRegime,
) -> dict[str, Any]:
    completed_windows = [
        f"{horizon}d"
        for horizon in (1, 5, 20)
        if any(str(row.get(f"evaluated_{horizon}d", "False")).lower() == "true" for row in signal_rows)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": run_date.isoformat(),
        "summary": {
            "sample_count": len(signal_rows),
            "decision_count": len(decisions),
            "completed_return_windows": completed_windows,
            "mode": "shadow_observational",
            "notes": [
                "Performance analytics are observational and do not change official decisions.",
                "Factor attribution is observed association, not causal proof.",
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
        "ai_recommendation_backtest": build_ai_recommendation_backtest(signal_rows),
    }


def _sync_web_public(source_path: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists() or not source_path.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_dir / source_path.name)
