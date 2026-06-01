"""Backfill decision metadata into legacy signal tracker rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.signal_tracker import FIELDNAMES, _write_rows, load_signal_rows

METADATA_FIELDS = (
    "conviction",
    "raw_conviction",
    "action",
    "regime",
    "sub_regime",
    "factors_json",
    "factor_reasoning_json",
    "confidence_meta_json",
)


@dataclass(frozen=True)
class SignalMetadataBackfillResult:
    rows: list[dict[str, str]]
    stats: dict[str, int]


def backfill_signal_metadata_file(
    signal_csv_path: Path,
    dashboard_history_path: Path,
    *,
    latest_index_path: Path | None = None,
) -> dict[str, int]:
    """Backfill a signal tracker CSV from finalized output history snapshots."""
    signal_rows = load_signal_rows(signal_csv_path)
    dashboard_history = _load_json_object(dashboard_history_path)
    latest_index = _load_json_object(latest_index_path) if latest_index_path and latest_index_path.exists() else None

    result = backfill_signal_metadata_rows(
        signal_rows,
        dashboard_history,
        latest_index_payload=latest_index,
    )
    _write_rows(signal_csv_path, result.rows)
    return result.stats


def backfill_signal_metadata_rows(
    signal_rows: list[dict[str, str]],
    dashboard_history_payload: dict[str, Any],
    *,
    latest_index_payload: dict[str, Any] | None = None,
) -> SignalMetadataBackfillResult:
    """Fill empty decision metadata fields by matching signal date and ticker."""
    snapshots = _snapshots_from_dashboard_history(dashboard_history_payload)
    if latest_index_payload:
        snapshots.update(_snapshots_from_latest_index(latest_index_payload))

    stats = {
        "source_snapshots": len(snapshots),
        "total_rows": len(signal_rows),
        "matched_rows": 0,
        "updated_rows": 0,
        "unmatched_rows": 0,
    }
    result_rows: list[dict[str, str]] = []

    for row in signal_rows:
        normalized = {name: str(row.get(name, "") or "") for name in FIELDNAMES}
        key = _row_key(normalized)
        snapshot = snapshots.get(key)
        if snapshot is None:
            stats["unmatched_rows"] += 1
            result_rows.append(normalized)
            continue

        stats["matched_rows"] += 1
        changed = False
        for field in METADATA_FIELDS:
            if str(normalized.get(field, "") or "").strip():
                continue
            value = snapshot.get(field, "")
            if value == "":
                continue
            normalized[field] = value
            changed = True
        if changed:
            stats["updated_rows"] += 1
        result_rows.append(normalized)

    return SignalMetadataBackfillResult(rows=result_rows, stats=stats)


def _snapshots_from_dashboard_history(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    snapshots: dict[tuple[str, str], dict[str, str]] = {}
    days = payload.get("days", [])
    if not isinstance(days, list):
        return snapshots

    for day in days:
        if not isinstance(day, dict):
            continue
        run_date = str(day.get("date", "") or "").strip()
        if not run_date:
            continue
        market_regime = day.get("market_regime") if isinstance(day.get("market_regime"), dict) else {}
        tickers = day.get("tickers", [])
        if not isinstance(tickers, list):
            continue
        for item in tickers:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "") or "").strip().upper()
            decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
            if not ticker or not decision:
                continue
            snapshots[(run_date, ticker)] = _metadata_from_decision(decision, market_regime)
    return snapshots


def _snapshots_from_latest_index(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    snapshots: dict[tuple[str, str], dict[str, str]] = {}
    run_date = str(payload.get("date", "") or "").strip()
    if not run_date:
        return snapshots
    market_regime = payload.get("market_regime") if isinstance(payload.get("market_regime"), dict) else {}
    tickers = payload.get("tickers", [])
    if not isinstance(tickers, list):
        return snapshots
    for item in tickers:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "") or "").strip().upper()
        decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
        if not ticker or not decision:
            continue
        snapshots[(run_date, ticker)] = _metadata_from_decision(decision, market_regime)
    return snapshots


def _metadata_from_decision(decision: dict[str, Any], market_regime: dict[str, Any]) -> dict[str, str]:
    conviction = _scalar_to_text(decision.get("conviction"))
    return {
        "conviction": conviction,
        "raw_conviction": _scalar_to_text(decision.get("raw_conviction", conviction)),
        "action": _scalar_to_text(decision.get("action")),
        "regime": _scalar_to_text(market_regime.get("regime")),
        "sub_regime": _scalar_to_text(market_regime.get("sub_regime")),
        "factors_json": _json_text(decision.get("factors")),
        "factor_reasoning_json": _json_text(decision.get("factor_reasoning")),
        "confidence_meta_json": _json_text(decision.get("confidence_meta")),
    }


def _row_key(row: dict[str, str]) -> tuple[str, str]:
    return (
        str(row.get("signal_date", "") or "").strip(),
        str(row.get("ticker", "") or "").strip().upper(),
    )


def _json_text(value: Any) -> str:
    if not isinstance(value, dict):
        return "{}"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _scalar_to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}
