from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.output.schema import SCHEMA_VERSION
from src.utils.datastore import get_datastore


def write_routing_outcome_output(
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    routing_history = _load_routing_history(data_dir)
    signal_rows = get_datastore(output_root=root).load_signal_rows_data()
    payload = _build_routing_outcome_payload(routing_history, signal_rows)

    path = data_dir / "routing_outcome.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_web_public_routing_outcome(path, root.parent)
    return payload


def _load_routing_history(data_dir: Path) -> list[dict[str, Any]]:
    history_path = data_dir / "routing_log_history.json"
    latest_path = data_dir / "routing_log.json"

    if history_path.exists():
        try:
            payload = json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            runs = payload.get("runs", [])
            if isinstance(runs, list):
                return [run for run in runs if isinstance(run, dict)]

    if latest_path.exists():
        try:
            payload = json.loads(latest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            return [payload]
    return []


def _build_routing_outcome_payload(
    routing_history: list[dict[str, Any]],
    signal_rows: list[dict[str, str]],
) -> dict[str, Any]:
    entries_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    latest_run_date = ""
    for run in routing_history:
        run_date = str(run.get("run_date", "")).strip()
        if run_date and run_date > latest_run_date:
            latest_run_date = run_date
        for entry in run.get("tickers", []):
            if not isinstance(entry, dict):
                continue
            ticker = str(entry.get("ticker", "")).strip().upper()
            if not ticker or not run_date:
                continue
            entries_by_key[(run_date, ticker)] = {
                "run_date": run_date,
                "ticker": ticker,
                "selected_for_deep": bool(entry.get("selected_for_deep", False)),
                "reason": str(entry.get("reason", "")),
                "conviction": entry.get("conviction"),
                "action": entry.get("action"),
                "in_portfolio": bool(entry.get("in_portfolio", False)),
            }

    evaluated_rows: list[dict[str, Any]] = []
    for row in signal_rows:
        run_date = str(row.get("signal_date", "")).strip()
        ticker = str(row.get("ticker", "")).strip().upper()
        if not run_date or not ticker:
            continue
        routing_entry = entries_by_key.get((run_date, ticker))
        if not routing_entry:
            continue
        if not _is_truthy(row.get("evaluated_20d", "")):
            continue
        return_20d = _parse_percent(row.get("return_20d", ""))
        if return_20d is None:
            continue

        evaluated_rows.append(
            {
                **routing_entry,
                "signal_direction": str(row.get("signal_direction", "")),
                "return_20d": return_20d,
                "catalyst_tag": str(row.get("catalyst_tag", "")),
                "trade_frame_scenario": str(row.get("trade_frame_scenario", "")),
            }
        )

    summary = _summarize_rows(evaluated_rows)
    periods = _build_period_rows(evaluated_rows)
    latest_run = _build_latest_run_snapshot(routing_history, latest_run_date)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_count": len(routing_history),
        "evaluated_signals": len(evaluated_rows),
        "latest_run_date": latest_run_date,
        "summary": summary,
        "periods": periods,
        "latest_run": latest_run,
        "status": "ok" if evaluated_rows else "no_data",
    }


def _build_period_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        period = str(row.get("run_date", ""))[:7]
        if not period:
            continue
        grouped[period].append(row)

    return [
        {"period": period, **_summarize_rows(period_rows)}
        for period, period_rows in sorted(grouped.items())
    ]


def _build_latest_run_snapshot(
    routing_history: list[dict[str, Any]],
    latest_run_date: str,
) -> dict[str, Any]:
    if not latest_run_date:
        return {}
    latest = next(
        (run for run in reversed(routing_history) if str(run.get("run_date", "")) == latest_run_date),
        None,
    )
    if not latest:
        return {}
    tickers = [
        {
            "ticker": str(entry.get("ticker", "")),
            "selected_for_deep": bool(entry.get("selected_for_deep", False)),
            "reason": str(entry.get("reason", "")),
            "in_portfolio": bool(entry.get("in_portfolio", False)),
            "conviction": entry.get("conviction"),
            "action": entry.get("action"),
            "router_priority_score": float(entry.get("router_priority_score", 0.0) or 0.0),
            "router_reason_codes": _string_list(entry.get("router_reason_codes")),
            "skipped_due_to_priority": bool(entry.get("skipped_due_to_priority", False)),
        }
        for entry in latest.get("tickers", [])
        if isinstance(entry, dict)
    ]
    return {
        "run_date": latest_run_date,
        "trigger_range": latest.get("trigger_range", []),
        "max_daily_ensemble": latest.get("max_daily_ensemble", 0),
        "portfolio_priority": bool(latest.get("portfolio_priority", False)),
        "deep_pass_count": int(latest.get("deep_pass_count", 0) or 0),
        "selected_tickers": _string_list(latest.get("selected_tickers")),
        "skipped_due_to_priority": _string_list(latest.get("skipped_due_to_priority")),
        "router_budget_estimate": latest.get("router_budget_estimate")
        if isinstance(latest.get("router_budget_estimate"), dict)
        else {},
        "tickers": tickers,
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deep_rows = [row for row in rows if row.get("selected_for_deep")]
    economy_rows = [row for row in rows if not row.get("selected_for_deep")]
    portfolio_priority_rows = [row for row in rows if row.get("reason") == "portfolio_priority"]

    deep_avg = _average_return(deep_rows)
    economy_avg = _average_return(economy_rows)
    deep_hit_rate = _hit_rate(deep_rows)
    economy_hit_rate = _hit_rate(economy_rows)
    portfolio_priority_avg = _average_return(portfolio_priority_rows)
    portfolio_priority_hit = _hit_rate(portfolio_priority_rows)

    return {
        "deep_selected_count": len(deep_rows),
        "economy_only_count": len(economy_rows),
        "portfolio_priority_count": len(portfolio_priority_rows),
        "deep_selected_avg_return_20d": deep_avg,
        "economy_only_avg_return_20d": economy_avg,
        "portfolio_priority_avg_return_20d": portfolio_priority_avg,
        "deep_selected_hit_rate": deep_hit_rate,
        "economy_only_hit_rate": economy_hit_rate,
        "portfolio_priority_hit_rate": portfolio_priority_hit,
        "avg_return_delta_20d": _rounded_or_none(
            None if deep_avg is None or economy_avg is None else deep_avg - economy_avg
        ),
        "hit_rate_delta": _rounded_or_none(
            None if deep_hit_rate is None or economy_hit_rate is None else deep_hit_rate - economy_hit_rate
        ),
    }


def _average_return(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    values = [float(row["return_20d"]) for row in rows]
    return _rounded_or_none(sum(values) / len(values))


def _hit_rate(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    winners = sum(1 for row in rows if float(row["return_20d"]) > 0)
    return _rounded_or_none((winners / len(rows)) * 100)


def _parse_percent(raw_value: str) -> float | None:
    text = str(raw_value or "").strip().replace("%", "").replace("+", "")
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _is_truthy(raw_value: str) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "y"}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _rounded_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _sync_web_public_routing_outcome(source_path: Path, project_root: Path) -> None:
    web_root = project_root / "web"
    if not web_root.exists() or not source_path.exists():
        return
    target_dir = web_root / "public" / "output" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_dir / source_path.name)
