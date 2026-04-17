from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.output.schema import SCHEMA_VERSION

def write_cost_log_output(
    *,
    output_root: Path | None = None,
    logs_root: Path | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    root = output_root or Path("output")
    summaries_root = logs_root or (Path("logs") / "pipeline")
    runs = _load_cost_runs(summaries_root, limit=limit)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "runs": runs,
        "latest": runs[0] if runs else {},
    }
    path = root / "data" / "cost_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_web_public_cost_log(path, root.parent)
    return payload


def _load_cost_runs(logs_root: Path, *, limit: int) -> list[dict[str, Any]]:
    if not logs_root.exists():
        return []

    runs: list[dict[str, Any]] = []
    for summary_path in sorted(logs_root.glob("*.summary.json"), reverse=True):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(summary, dict):
            continue

        run_date = str(summary.get("run_date", summary_path.stem.replace(".summary", "")))
        jsonl_path = logs_root / f"{run_date}.jsonl"
        event_payload = _load_event_metrics(jsonl_path)
        total_cost = float(summary.get("daily_api_cost_usd", 0.0) or 0.0)
        profile_costs = event_payload["profile_costs"]
        profile_tokens = event_payload["profile_tokens"]
        routing = event_payload["routing"]

        deep_cost = float(profile_costs.get("deep", 0.0) or 0.0)
        deep_selected = int(routing.get("selected_count", 0) or 0)
        deep_cost_per_ticker = round(deep_cost / deep_selected, 6) if deep_selected else 0.0
        deep_share_of_total = round(deep_cost / total_cost, 4) if total_cost else 0.0

        runs.append(
            {
                "run_date": run_date,
                "success": bool(summary.get("success", False)),
                "total_cost_usd": round(total_cost, 8),
                "profiles": {
                    profile: {
                        "cost_usd": round(float(cost or 0.0), 8),
                        "tokens": int(profile_tokens.get(profile, 0) or 0),
                        "calls": int(event_payload["profile_calls"].get(profile, 0) or 0),
                        "models": dict(sorted(event_payload["profile_models"].get(profile, {}).items())),
                    }
                    for profile, cost in sorted(profile_costs.items())
                },
                "routing": routing,
                "deep_pass_value": {
                    "deep_cost_usd": round(deep_cost, 8),
                    "selected_ticker_count": deep_selected,
                    "cost_per_selected_ticker_usd": deep_cost_per_ticker,
                    "share_of_total_cost": deep_share_of_total,
                    "worth_it_hint": _classify_deep_value(
                        deep_cost=deep_cost,
                        deep_selected=deep_selected,
                        conflicted_count=int(routing.get("conflicted_count", 0) or 0),
                    ),
                },
            }
        )
        if len(runs) >= limit:
            break
    return runs


def _load_event_metrics(jsonl_path: Path) -> dict[str, Any]:
    profile_costs: dict[str, float] = defaultdict(float)
    profile_tokens: dict[str, int] = defaultdict(int)
    profile_calls: dict[str, int] = defaultdict(int)
    profile_models: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    routing: dict[str, Any] = {
        "ensemble_enabled": False,
        "eligible_count": 0,
        "selected_count": 0,
        "skipped_due_to_cap_count": 0,
        "conflicted_count": 0,
    }

    if not jsonl_path.exists():
        return {
            "profile_costs": profile_costs,
            "profile_tokens": profile_tokens,
            "profile_calls": profile_calls,
            "profile_models": profile_models,
            "routing": routing,
        }

    for raw_line in jsonl_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue

        event = str(row.get("event", ""))
        if event == "openai_usage_recorded":
            profile = str(row.get("model_profile", "unknown")).strip() or "unknown"
            model = str(row.get("model", "unknown")).strip() or "unknown"
            profile_costs[profile] += float(row.get("estimated_cost_usd", 0.0) or 0.0)
            profile_tokens[profile] += int(row.get("total_tokens", 0) or 0)
            profile_calls[profile] += 1
            profile_models[profile][model] += 1
        elif event == "decision_completed":
            routing = {
                "ensemble_enabled": bool(row.get("ensemble_enabled", False)),
                "eligible_count": int(row.get("ensemble_eligible_count", 0) or 0),
                "selected_count": int(row.get("ensemble_selected_count", 0) or 0),
                "skipped_due_to_cap_count": int(row.get("ensemble_skipped_due_to_cap", 0) or 0),
                "conflicted_count": int(row.get("ensemble_conflicted_count", 0) or 0),
            }

    return {
        "profile_costs": profile_costs,
        "profile_tokens": profile_tokens,
        "profile_calls": profile_calls,
        "profile_models": profile_models,
        "routing": routing,
    }


def _classify_deep_value(*, deep_cost: float, deep_selected: int, conflicted_count: int) -> str:
    if deep_selected <= 0 or deep_cost <= 0:
        return "deep_pass_unused"
    if conflicted_count > 0:
        return "conflict_review_value"
    if deep_cost / max(deep_selected, 1) <= 0.05:
        return "efficient"
    if deep_cost / max(deep_selected, 1) <= 0.15:
        return "acceptable"
    return "expensive"


def _sync_web_public_cost_log(source_path: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists() or not source_path.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_dir / source_path.name)
