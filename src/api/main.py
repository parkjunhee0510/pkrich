from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.chat.engine import answer_question

OUTPUT_ROOT = Path("output")

app = FastAPI(title="pkrich API", version="0.1.0")


class ChatRequest(BaseModel):
    question: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/daily")
def daily() -> dict[str, Any]:
    return _load_json(OUTPUT_ROOT / "data" / "dashboard.json", default={"days": []})


@app.get("/api/ticker/{ticker}")
def ticker_detail(ticker: str) -> dict[str, Any]:
    payload = _load_json(OUTPUT_ROOT / "data" / "dashboard.json", default={"days": []})
    days = payload.get("days", [])
    if not days:
        raise HTTPException(status_code=404, detail="No daily data available")
    latest_day = days[-1]
    for entry in latest_day.get("tickers", []):
        if str(entry.get("ticker", "")).upper() == ticker.upper():
            return entry
    raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")


@app.get("/api/signals")
def signals() -> dict[str, Any]:
    payload = _load_json(OUTPUT_ROOT / "data" / "dashboard.json", default={"signal_stats": {}})
    return payload.get("signal_stats", {})


@app.get("/api/backtest")
def backtest() -> dict[str, Any]:
    return _load_json(OUTPUT_ROOT / "data" / "backtest_summary.json", default={"status": "no_data"})


@app.get("/api/monthly")
def monthly() -> dict[str, Any]:
    return _load_json(OUTPUT_ROOT / "data" / "monthly_summary.json", default={"status": "no_data"})


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    return answer_question(request.question, output_root=OUTPUT_ROOT)


def _load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
