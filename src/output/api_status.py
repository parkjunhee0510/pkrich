from __future__ import annotations

import csv
import json
import shutil
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

from src.types import WatchlistItem
from src.utils.pipeline_logging import record_pipeline_event

_PROVIDERS = ("yfinance", "alpha_vantage", "polygon", "fmp", "finnhub", "sec_edgar", "ir_rss")

# OneDrive / antivirus occasionally holds a brief sync lock on files in
# `output/data/`, which surfaces as OSError (Errno 13 / 22 / 32) when the
# pipeline writes several files back-to-back. Retry with small backoff so a
# transient lock doesn't kill the run.
_RETRY_DELAYS = (0.1, 0.3, 0.7)


def _retry_io(op: Callable[[], None], *, what: str) -> None:
    """Retry a filesystem op on transient OSError (OneDrive / AV sync locks)."""
    last_err: OSError | None = None
    for delay in (0.0, *_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            op()
            return
        except OSError as err:
            last_err = err
    # Give up — re-raise with context for the pipeline error log.
    assert last_err is not None
    raise OSError(f"{what} failed after {len(_RETRY_DELAYS)} retries: {last_err}") from last_err


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

    payload = build_api_status_payload(run_date, watchlist, logs_root=logs_root, output_root=root)
    status_path = data_dir / "api_status.json"
    matrix_json_path = data_dir / "api_ticker_matrix.json"
    matrix_csv_path = data_dir / "api_ticker_matrix.csv"

    _retry_io(
        lambda: status_path.write_text(
            json.dumps(payload["summary"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        ),
        what=f"write {status_path}",
    )
    _retry_io(
        lambda: matrix_json_path.write_text(
            json.dumps(payload["ticker_matrix"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        ),
        what=f"write {matrix_json_path}",
    )
    _retry_io(
        lambda: _write_matrix_csv(matrix_csv_path, payload["ticker_matrix"]),
        what=f"write {matrix_csv_path}",
    )
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
    output_root: Path | None = None,
) -> dict[str, Any]:
    log_path = (logs_root or (Path("logs") / "pipeline")) / f"{run_date.isoformat()}.jsonl"
    last_run = _load_last_run_rows(log_path)
    overall_provider_usage = _collect_overall_provider_usage(last_run)
    per_ticker = _build_ticker_provider_state(last_run, watchlist, overall_provider_usage=overall_provider_usage)
    provider_summary = _summarize_providers(per_ticker, overall_provider_usage=overall_provider_usage)
    llm_summary = _summarize_llm(last_run, output_root=output_root)
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
    *,
    overall_provider_usage: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    states: dict[str, dict[str, str]] = {
        item.ticker: {provider: "not_used" for provider in _PROVIDERS}
        for item in watchlist
    }
    overall_provider_usage = overall_provider_usage or set()

    for row in rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        event = str(row.get("event", ""))
        source = str(row.get("source", ""))
        level = str(row.get("level", ""))

        if event == "data_provider_used" and ticker and ticker in states:
            if source in {"yfinance", "alpha_vantage", "polygon"}:
                states[ticker][source] = "used"
            continue

        if event == "polygon_options_flow" and ticker and ticker in states:
            states[ticker]["polygon"] = "used"
            continue
        if event == "polygon_options_flow_failed" and ticker and ticker in states:
            states[ticker]["polygon"] = "failed"
            continue

        if event.startswith("fmp_") and ticker and ticker in states:
            _merge_status(states[ticker], "fmp", _classify_event_status(event, level))
            continue

        if event.startswith("finnhub_") and ticker and ticker in states:
            _merge_status(states[ticker], "finnhub", _classify_event_status(event, level))
            continue

        if event == "news_provider_completed" and ticker and ticker in states and source == "SEC EDGAR":
            states[ticker]["sec_edgar"] = "used"
            continue

        if event == "news_provider_completed" and ticker and ticker in states and source and source != "SEC EDGAR":
            states[ticker]["ir_rss"] = "used"
            continue

        if event == "news_collection_completed" and ticker and ticker in states:
            try:
                if int(row.get("sec_result_count", 0) or 0) > 0:
                    states[ticker]["sec_edgar"] = "used"
                if int(row.get("ir_result_count", 0) or 0) > 0:
                    states[ticker]["ir_rss"] = "used"
            except (TypeError, ValueError):
                continue

        if event == "ticker_events_normalized" and ticker and ticker in states and source.startswith("alpha_vantage"):
            states[ticker]["alpha_vantage"] = "used"

    # yfinance is the primary collector in the orchestrated path, but some runs
    # only log it at the provider-summary level rather than per ticker. If the
    # run-level provider set includes yfinance and we saw no per-ticker usage,
    # treat watchlist tickers as yfinance-backed for this run.
    if "yfinance" in overall_provider_usage:
        if all(statuses.get("yfinance") == "not_used" for statuses in states.values()):
            for ticker in states:
                states[ticker]["yfinance"] = "used"

    return states


def _collect_overall_provider_usage(rows: list[dict[str, Any]]) -> set[str]:
    providers_used: set[str] = set()
    for row in rows:
        event = str(row.get("event", ""))
        source = str(row.get("source", ""))

        if event == "data_provider_used" and source in _PROVIDERS:
            providers_used.add(source)
            continue

        if event == "ticker_events_normalized" and source.startswith("alpha_vantage"):
            providers_used.add("alpha_vantage")
            continue

        if event == "polygon_options_flow":
            providers_used.add("polygon")
            continue

        if event == "orchestrator_primary_completed":
            raw_providers = row.get("providers_used", [])
            if isinstance(raw_providers, list):
                for provider in raw_providers:
                    provider_name = str(provider).strip()
                    if provider_name in _PROVIDERS:
                        providers_used.add(provider_name)

    return providers_used


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


def _summarize_providers(
    per_ticker: dict[str, dict[str, str]],
    *,
    overall_provider_usage: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    overall_provider_usage = overall_provider_usage or set()
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
        elif provider in overall_provider_usage:
            overall = "active"
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


def _summarize_llm(rows: list[dict[str, Any]], *, output_root: Path | None = None) -> dict[str, Any]:
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

    quality_latest = _load_analysis_quality_latest(output_root)
    return {
        "used": bool(usage_rows),
        "planned_batches": len(planned_batches),
        "completed_batches": len(usage_rows),
        "failed_batches": len(request_failures),
        "validation_failures": len(validation_failures),
        "estimated_cost_usd": round(estimated_cost, 8),
        "latest_model": str(latest_usage.get("model", "")).strip() or "N/A",
        "models_used": dict(sorted(models.items())),
        "quality": quality_latest,
    }


def _load_analysis_quality_latest(output_root: Path | None) -> dict[str, Any]:
    root = output_root or Path("output")
    quality_path = root / "data" / "analysis_quality.json"
    if not quality_path.exists():
        return {}
    try:
        payload = json.loads(quality_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    latest = payload.get("latest", {})
    return latest if isinstance(latest, dict) else {}


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
            target_path = target_dir / filename
            _retry_io(
                lambda s=source_path, t=target_path: shutil.copy2(s, t),
                what=f"sync {target_path}",
            )
