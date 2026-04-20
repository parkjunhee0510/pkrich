from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_analysis_quality_output(
    *,
    output_root: Path | None = None,
    logs_root: Path | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    root = output_root or Path("output")
    summaries_root = logs_root or (Path("logs") / "pipeline")
    runs = _load_quality_runs(summaries_root, limit=limit)
    latest = runs[0] if runs else {}
    payload = {
        "runs": runs,
        "latest": latest,
    }
    path = root / "data" / "analysis_quality.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _load_quality_runs(logs_root: Path, *, limit: int) -> list[dict[str, Any]]:
    if not logs_root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for summary_path in sorted(logs_root.glob("*.summary.json"), reverse=True):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        analyzer_quality = payload.get("analyzer_quality", {}) if isinstance(payload, dict) else {}
        if not isinstance(analyzer_quality, dict):
            analyzer_quality = {}
        validated_ticker_count = int(analyzer_quality.get("validated_ticker_count", 0) or 0)
        hallucination_warning_count = int(analyzer_quality.get("hallucination_warning_count", 0) or 0)
        hallucination_ratio = round(hallucination_warning_count / validated_ticker_count, 4) if validated_ticker_count else 0.0
        runs.append(
            {
                "run_date": payload.get("run_date", summary_path.stem.replace(".summary", "")),
                "success": bool(payload.get("success", False)),
                "daily_api_cost_usd": payload.get("daily_api_cost_usd", 0.0),
                "batch_count": int(analyzer_quality.get("batch_count", 0) or 0),
                "validated_ticker_count": validated_ticker_count,
                "validation_failure_count": int(analyzer_quality.get("validation_failure_count", 0) or 0),
                "schema_violation_count": int(analyzer_quality.get("schema_violation_count", 0) or 0),
                "fact_warning_count": int(analyzer_quality.get("fact_warning_count", 0) or 0),
                "consistency_warning_count": int(analyzer_quality.get("consistency_warning_count", 0) or 0),
                "hallucination_warning_count": hallucination_warning_count,
                "hallucination_ratio": hallucination_ratio,
            }
        )
        if len(runs) >= limit:
            break
    return runs
