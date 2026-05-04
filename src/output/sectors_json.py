"""Serialize `SectorSnapshot` list → `output/data/sectors.json`.

Read by the React `/sectors` page. Shape intentionally flat so the frontend
needs no post-processing beyond routing by `id`.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from src.collector.sector_scan import SectorSnapshot
from src.output.schema import SCHEMA_VERSION


def write_sectors_json(
    sectors: list[SectorSnapshot],
    run_date: date,
    *,
    output_root: Path | None = None,
) -> Path:
    """Write `<output_root>/data/sectors.json`. Returns the file path."""
    root = output_root or Path("output")
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "sectors.json"

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": run_date.isoformat(),
        "sectors": [_sector_to_dict(sector) for sector in sectors],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _sector_to_dict(sector: SectorSnapshot) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": sector.id,
        "name": sector.name,
        "description": sector.description,
        "tickers": [_ticker_to_dict(t) for t in sector.tickers],
    }
    if sector.benchmark is not None:
        payload["benchmark"] = _benchmark_to_dict(sector.benchmark)
    return payload


def _benchmark_to_dict(benchmark: Any) -> dict[str, Any]:
    raw = asdict(benchmark)
    return {
        "ticker": raw.get("ticker", ""),
        "name": raw.get("name", ""),
        "price": raw.get("price", ""),
        "currency": raw.get("currency", ""),
        "change_percent": raw.get("change_percent", ""),
        "history": [
            {"date": point["date"], "close": point["close"]}
            for point in raw.get("history", [])
        ],
        "error": raw.get("error", ""),
    }


def _ticker_to_dict(ticker: Any) -> dict[str, Any]:
    raw = asdict(ticker)
    # dataclass.asdict recurses into the `history` and `news` lists already;
    # just normalize types for JSON (no datetime, no NaN).
    return {
        "ticker": raw.get("ticker", ""),
        "name": raw.get("name", ""),
        "price": raw.get("price", ""),
        "currency": raw.get("currency", ""),
        "change_percent": raw.get("change_percent", ""),
        "history": [
            {"date": point["date"], "close": point["close"]}
            for point in raw.get("history", [])
        ],
        "news": [
            {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "link": item.get("link", ""),
            }
            for item in raw.get("news", [])
        ],
        "error": raw.get("error", ""),
    }
