from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PipelineEvent:
    date: date
    component: str
    severity: str
    message: str
    detail: Mapping[str, Any]
    ticker: str | None = None
    module: str | None = None


@dataclass(frozen=True)
class AuditDataset:
    window_start: date
    window_end: date
    tickers: tuple[str, ...]
    daily: Mapping[str, Mapping[date, dict]]
    logs: tuple[PipelineEvent, ...]
    summaries: Mapping[date, dict]
    llm_evidence: Mapping[date, tuple[dict[str, Any], ...]]
    model_profile: str


def _read_json(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _record_date(payload: dict[str, Any]) -> date | None:
    raw_date = payload.get("date")
    if raw_date is None and isinstance(payload.get("payload"), dict):
        raw_date = payload["payload"].get("date")
    try:
        return date.fromisoformat(str(raw_date))
    except (TypeError, ValueError):
        return None


def _read_jsonl(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _events_from_jsonl(rows: list[dict[str, Any]], d: date) -> list[PipelineEvent]:
    events: list[PipelineEvent] = []
    for row in rows:
        events.append(PipelineEvent(
            date=d,
            component=row.get("component", "unknown"),
            severity=row.get("severity", "info"),
            message=row.get("message", ""),
            detail=row.get("detail") or {},
            ticker=row.get("ticker"),
            module=row.get("module"),
        ))
    return events


def load_window(
    *,
    root: Path,
    end: date,
    window_days: int,
    tickers: list[str],
    model_profile: str,
) -> AuditDataset:
    if window_days < 1:
        raise ValueError(f"window_days must be >= 1, got {window_days}")
    start = end - timedelta(days=window_days - 1)
    days = [start + timedelta(days=i) for i in range(window_days)]

    daily: dict[str, dict[date, dict]] = {}
    for ticker in tickers:
        per_day: dict[date, dict] = {}
        base = root / "output" / "data" / "tickers" / ticker / "daily"
        for d in days:
            payload = _read_json(base / f"{d.isoformat()}.json")
            if payload is not None:
                per_day[d] = payload
        latest_payload = _read_json(root / "output" / "data" / "tickers" / ticker / "latest.json")
        if latest_payload is not None:
            latest_date = _record_date(latest_payload)
            if latest_date in days and latest_date not in per_day:
                per_day[latest_date] = latest_payload
        daily[ticker] = per_day

    summaries: dict[date, dict] = {}
    logs: list[PipelineEvent] = []
    log_root = root / "logs" / "pipeline"
    for d in days:
        s = _read_json(log_root / f"{d.isoformat()}.summary.json")
        if s is not None:
            summaries[d] = s
        rows = _read_jsonl(log_root / f"{d.isoformat()}.jsonl")
        logs.extend(_events_from_jsonl(rows, d))

    llm_evidence: dict[date, tuple[dict[str, Any], ...]] = {}
    evidence_root = root / "output" / "data" / "llm_evidence"
    for d in days:
        llm_evidence[d] = tuple(_read_jsonl(evidence_root / f"{d.isoformat()}.jsonl"))

    return AuditDataset(
        window_start=start,
        window_end=end,
        tickers=tuple(tickers),
        daily=daily,
        logs=tuple(logs),
        summaries=summaries,
        llm_evidence=llm_evidence,
        model_profile=model_profile,
    )
