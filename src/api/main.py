from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.chat.engine import answer_question
from src.utils.datastore import get_datastore

OUTPUT_ROOT = Path("output")

app = FastAPI(title="pkrich API", version="0.1.0")


class ChatRequest(BaseModel):
    question: str
    messages: list[dict[str, str]] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/daily")
def daily() -> dict[str, Any]:
    return _load_dashboard_payload()


@app.get("/api/ticker/{ticker}")
def ticker_detail(ticker: str) -> dict[str, Any]:
    shard_path = OUTPUT_ROOT / "data" / "tickers" / ticker.upper() / "latest.json"
    shard = _load_json(shard_path, default={})
    payload = shard.get("payload") if isinstance(shard, dict) else None
    if isinstance(payload, dict):
        history = _get_datastore().get_ticker_history(ticker)
        if history:
            return {**payload, "history": history}
        return payload

    latest_day = _load_latest_day()
    for entry in latest_day.get("tickers", []):
        if str(entry.get("ticker", "")).upper() == ticker.upper():
            history = _get_datastore().get_ticker_history(ticker)
            if history:
                return {**entry, "history": history}
            return entry
    raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")


@app.get("/api/ticker/{ticker}/history")
def ticker_history(ticker: str) -> dict[str, Any]:
    history = _get_datastore().get_ticker_history(ticker)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history found for {ticker}")
    return {"ticker": ticker.upper(), "history": history}


@app.get("/api/signals")
def signals() -> dict[str, Any]:
    signal_stats = _get_datastore().get_signal_stats()
    if signal_stats is not None:
        return signal_stats
    payload = _load_dashboard_payload()
    return payload.get("signal_stats", {})


@app.get("/api/backtest")
def backtest() -> dict[str, Any]:
    return _load_json(OUTPUT_ROOT / "data" / "backtest_summary.json", default={"status": "no_data"})


@app.get("/api/monthly")
def monthly() -> dict[str, Any]:
    return _load_json(OUTPUT_ROOT / "data" / "monthly_summary.json", default={"status": "no_data"})


@app.get("/api/analytics/quality")
def analytics_quality() -> dict[str, Any]:
    quality_runs = _get_datastore().get_analysis_quality()
    if not quality_runs:
        quality_runs = _load_analysis_runs_from_logs()
    return {"runs": quality_runs}


@app.get("/api/analytics/cost")
def analytics_cost() -> dict[str, Any]:
    runs = _get_datastore().get_analysis_quality()
    if not runs:
        runs = _load_analysis_runs_from_logs()
    cost_log = _load_json(OUTPUT_ROOT / "data" / "cost_log.json", default={"runs": [], "latest": {}})
    total_cost = sum(float(run.get("daily_api_cost_usd", 0.0) or 0.0) for run in runs)
    successful_runs = sum(1 for run in runs if bool(run.get("success")))
    return {
        "runs": runs,
        "total_cost_usd": round(total_cost, 6),
        "average_cost_usd": round(total_cost / len(runs), 6) if runs else 0.0,
        "successful_runs": successful_runs,
        "cost_log": cost_log,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    return answer_question(request.question, output_root=OUTPUT_ROOT, messages=request.messages)


def _load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_dashboard_payload() -> dict[str, Any]:
    index_payload = _load_json(OUTPUT_ROOT / "data" / "index.json", default={})
    if isinstance(index_payload, dict) and index_payload.get("date"):
        return {
            "schema_version": index_payload.get("schema_version"),
            "days": [
                {
                    "date": index_payload.get("date", ""),
                    "market_overview": index_payload.get("market_overview", []),
                    "macro_context": index_payload.get("macro_context", {}),
                    "market_regime": index_payload.get("market_regime", {}),
                    "pm_view": index_payload.get("pm_view"),
                    "portfolio_summary": index_payload.get("portfolio_summary"),
                    "portfolio_risk": index_payload.get("portfolio_risk", {}),
                    "tickers": index_payload.get("tickers", []),
                }
            ],
            "signal_stats": index_payload.get("signal_stats", {}),
            "weekly_summary": index_payload.get("weekly_summary", {}),
        }
    return _load_json(OUTPUT_ROOT / "data" / "dashboard.json", default={"days": []})


def _load_latest_day() -> dict[str, Any]:
    payload = _load_dashboard_payload()
    days = payload.get("days", [])
    if not days:
        raise HTTPException(status_code=404, detail="No daily data available")
    return days[-1]


def _get_datastore():
    return get_datastore(output_root=OUTPUT_ROOT)


def _load_analysis_runs_from_logs(limit: int = 30) -> list[dict[str, Any]]:
    logs_dir = OUTPUT_ROOT.parent / "logs" / "pipeline"
    if not logs_dir.exists():
        return []
    runs: list[dict[str, Any]] = []
    for summary_path in sorted(logs_dir.glob("*.summary.json"), reverse=True):
        payload = _load_json(summary_path, default={})
        if not isinstance(payload, dict):
            continue
        runs.append(
            {
                "run_date": payload.get("run_date", summary_path.stem.replace(".summary", "")),
                "success": bool(payload.get("success", False)),
                "daily_api_cost_usd": payload.get("daily_api_cost_usd", 0.0),
                "models_used": payload.get("models_used", {}),
                "llm_usage": payload.get("llm_usage", {}),
                "batch_count": payload.get("analyzer_quality", {}).get("batch_count", 0),
                "fallback_count": len(payload.get("ticker_fallbacks", {})),
                "validation_failure_count": payload.get("analyzer_quality", {}).get("validation_failure_count", 0),
            }
        )
        if len(runs) >= limit:
            break
    return runs
