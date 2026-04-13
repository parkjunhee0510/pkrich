from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from src.types import WatchlistItem
from src.utils.pipeline_logging import record_pipeline_event

_PROVIDERS = ("yfinance", "alpha_vantage", "polygon", "fmp", "finnhub", "sec_edgar", "ir_rss")


def write_api_status_outputs(
    run_date: date,
    watchlist: list[WatchlistItem],
    *,
    output_root: Path | None = None,
    logs_root: Path | None = None,
) -> dict[str, Path]:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = build_api_status_payload(run_date, watchlist, logs_root=logs_root)
    status_path = data_dir / "api_status.json"
    matrix_json_path = data_dir / "api_ticker_matrix.json"
    matrix_csv_path = data_dir / "api_ticker_matrix.csv"

    status_path.write_text(json.dumps(payload["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    matrix_json_path.write_text(json.dumps(payload["ticker_matrix"], ensure_ascii=False, indent=2), encoding="utf-8")
    _write_matrix_csv(matrix_csv_path, payload["ticker_matrix"])
    _sync_web_public_data(data_dir, root.parent)

    for artifact, path in (
        ("api_status", status_path),
        ("api_ticker_matrix_json", matrix_json_path),
        ("api_ticker_matrix_csv", matrix_csv_path),
    ):
        record_pipeline_event("output", "info", "artifact_written", artifact=artifact, path=str(path), ticker="")

    return {
        "api_status": status_path,
        "api_ticker_matrix_json": matrix_json_path,
        "api_ticker_matrix_csv": matrix_csv_path,
    }


def build_api_status_payload(
    run_date: date,
    watchlist: list[WatchlistItem],
    *,
    logs_root: Path | None = None,
) -> dict[str, Any]:
    log_path = (logs_root or (Path("logs") / "pipeline")) / f"{run_date.isoformat()}.jsonl"
    last_run = _load_last_run_rows(log_path)
    per_ticker = _build_ticker_provider_state(last_run, watchlist)
    provider_summary = _summarize_providers(per_ticker)
    llm_summary = _summarize_llm(last_run)
    return {
        "summary": {
            "run_date": run_date.isoformat(),
            "log_path": str(log_path),
            "pipeline_completed": any(row.get("event") == "pipeline_completed" for row in last_run),
            "providers": provider_summary,
            "llm": llm_summary,
        },
        "ticker_matrix": [
            {
                "ticker": item.ticker,
                "name": item.name,
                "sector": item.sector,
                **per_ticker[item.ticker],
            }
            for item in watchlist
        ],
    }


def _load_last_run_rows(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    starts = [index for index, row in enumerate(rows) if row.get("event") == "pipeline_started"]
    if not starts:
        return rows
    return rows[starts[-1]:]


def _build_ticker_provider_state(
    rows: list[dict[str, Any]],
    watchlist: list[WatchlistItem],
) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {
        item.ticker: {provider: "not_used" for provider in _PROVIDERS}
        for item in watchlist
    }

    for row in rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker or ticker not in states:
            continue

        event = str(row.get("event", ""))
        source = str(row.get("source", ""))
        level = str(row.get("level", ""))

        if event == "data_provider_used":
            if source in {"yfinance", "alpha_vantage"}:
                states[ticker][source] = "used"
            continue

        if event == "polygon_options_flow":
            states[ticker]["polygon"] = "used"
            continue
        if event == "polygon_options_flow_failed":
            states[ticker]["polygon"] = "failed"
            continue

        if event.startswith("fmp_"):
            _merge_status(states[ticker], "fmp", _classify_event_status(event, level))
            continue

        if event.startswith("finnhub_"):
            _merge_status(states[ticker], "finnhub", _classify_event_status(event, level))
            continue

        if event == "news_provider_completed" and source == "SEC EDGAR":
            states[ticker]["sec_edgar"] = "used"
            continue

        if event == "news_provider_completed" and source and source != "SEC EDGAR":
            states[ticker]["ir_rss"] = "used"
            continue

        if event == "news_collection_completed":
            try:
                if int(row.get("sec_result_count", 0) or 0) > 0:
                    states[ticker]["sec_edgar"] = "used"
                if int(row.get("ir_result_count", 0) or 0) > 0:
                    states[ticker]["ir_rss"] = "used"
            except (TypeError, ValueError):
                continue

    return states


def _classify_event_status(event: str, level: str) -> str:
    if event.endswith("_throttled"):
        return "throttled"
    if event.endswith("_failed") or level == "warning":
        return "failed"
    if event.endswith("_unavailable"):
        return "unavailable"
    return "used"


def _merge_status(target: dict[str, str], provider: str, new_status: str) -> None:
    priority = {"failed": 4, "used": 3, "throttled": 2, "unavailable": 1, "not_used": 0}
    current = target.get(provider, "not_used")
    if priority[new_status] > priority[current]:
        target[provider] = new_status


def _summarize_providers(per_ticker: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for provider in _PROVIDERS:
        counts = Counter(statuses.get(provider, "not_used") for statuses in per_ticker.values())
        if counts.get("used", 0) > 0 and counts.get("failed", 0) == 0:
            overall = "partial" if counts.get("throttled", 0) > 0 else "active"
        elif counts.get("used", 0) > 0 and counts.get("failed", 0) > 0:
            overall = "partial"
        elif counts.get("throttled", 0) > 0:
            overall = "limited"
        elif counts.get("unavailable", 0) > 0:
            overall = "limited"
        elif counts.get("failed", 0) > 0:
            overall = "failing"
        else:
            overall = "idle"
        result[provider] = {
            "overall_status": overall,
            "used_tickers": counts.get("used", 0),
            "throttled_tickers": counts.get("throttled", 0),
            "unavailable_tickers": counts.get("unavailable", 0),
            "failed_tickers": counts.get("failed", 0),
            "not_used_tickers": counts.get("not_used", 0),
        }
    return result


def _summarize_llm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    planned_batches = [row for row in rows if row.get("event") == "analysis_batch_planned"]
    usage_rows = [row for row in rows if row.get("event") == "openai_usage_recorded"]
    request_failures = [row for row in rows if row.get("event") in {"openai_request_failed", "openai_analyzer_failed"}]
    validation_failures = [row for row in rows if row.get("event") == "openai_response_validation_failed"]

    models = Counter(str(row.get("model", "")).strip() for row in usage_rows if str(row.get("model", "")).strip())
    latest_usage = usage_rows[-1] if usage_rows else {}
    estimated_cost = 0.0
    for row in usage_rows:
        try:
            estimated_cost += float(row.get("estimated_cost_usd") or 0.0)
        except (TypeError, ValueError):
            continue

    return {
        "used": bool(usage_rows),
        "planned_batches": len(planned_batches),
        "completed_batches": len(usage_rows),
        "failed_batches": len(request_failures),
        "validation_failures": len(validation_failures),
        "estimated_cost_usd": round(estimated_cost, 8),
        "latest_model": str(latest_usage.get("model", "")).strip() or "N/A",
        "models_used": dict(sorted(models.items())),
    }


def _write_matrix_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["ticker", "name", "sector", *_PROVIDERS]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _sync_web_public_data(data_dir: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists():
        return

    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("api_status.json", "api_ticker_matrix.json", "api_ticker_matrix.csv"):
        source_path = data_dir / filename
        if source_path.exists():
            shutil.copy2(source_path, target_dir / filename)
