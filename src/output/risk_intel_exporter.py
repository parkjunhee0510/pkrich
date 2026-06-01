"""Export public risk intelligence JSON artifacts from the SQLite store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.output.risk_intel_builder import (
    build_risk_intel_refresh_log_from_graph,
    build_risk_intel_summary_from_graph,
)
from src.output.risk_intel_store import load_graph_run, load_refresh_requests


def export_risk_intel_artifacts(db_path: Path, *, run_id: str | None = None) -> dict[str, dict[str, Any]]:
    graph = load_graph_run(db_path, run_id=run_id)
    refresh_runs = load_refresh_requests(db_path, str(graph["generation"]["run_id"]))
    summary = build_risk_intel_summary_from_graph(graph)
    refresh_log = build_risk_intel_refresh_log_from_graph(graph, refresh_runs=refresh_runs)
    return {"graph": graph, "summary": summary, "refresh_log": refresh_log}
