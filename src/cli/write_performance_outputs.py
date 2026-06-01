"""CLI for writing performance baseline, trends, and report artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from src.output.performance import write_performance_outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write performance baseline, trend, report, and web mirror artifacts.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root containing output/data and web/public/output/data.",
    )
    parser.add_argument(
        "--run-date",
        default=None,
        help="Run date for the report and payload as_of field, formatted YYYY-MM-DD.",
    )
    parser.add_argument(
        "--monthly-budget-usd",
        type=float,
        default=None,
        help="Monthly budget used for budget usage diagnostics. Defaults to config/models.yaml budget_guard.monthly_cap_usd.",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    run_date = date.fromisoformat(args.run_date) if args.run_date else None
    result = write_performance_outputs(
        output_root=project_root / "output",
        logs_root=project_root / "logs" / "pipeline",
        project_root=project_root,
        run_date=run_date,
        monthly_budget_usd=args.monthly_budget_usd,
    )
    baseline = _load_json(result["baseline_path"])
    summary = {
        "status": str(baseline.get("status", "")),
        "latest_run_date": str(baseline.get("latest_run_date", "")),
        "baseline_path": str(result["baseline_path"]),
        "trends_path": str(result["trends_path"]),
        "quality_loop_path": str(result["quality_loop_path"]),
        "report_path": str(result["report_path"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
