from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from src.eval.data_sources import AuditDataset, PipelineEvent


def make_daily(
    *,
    ticker: str,
    as_of: date,
    summary: str = "Test summary 100.00 USD (+0.50%).",
    key_news: Sequence[str] | None = None,
    news_references: Sequence[Mapping[str, str]] | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ticker": ticker,
        "name": f"{ticker} Inc.",
        "date": as_of.isoformat(),
        "summary": summary,
        "key_news": list(key_news or [f"{ticker} headline 1"]),
        "news_references": list(news_references or [
            {"title": f"{ticker} headline 1", "source": "Reuters",
             "published_at": as_of.isoformat(),
             "link": f"https://example.com/{ticker}/1"}
        ]),
    }
    if extra_payload:
        payload.update(extra_payload)
    return {
        "schema_version": 1,
        "date": as_of.isoformat(),
        "ticker": ticker,
        "payload": payload,
    }


def make_summary(
    as_of: date,
    *,
    fallback_count: int = 0,
    schema_retry_count: int = 0,
    token_usage: Mapping[str, int] | None = None,
    daily_api_cost_usd: float = 0.10,
) -> dict[str, Any]:
    return {
        "date": as_of.isoformat(),
        "components": {},
        "fallback_count": fallback_count,
        "schema_retry_count": schema_retry_count,
        "model_usage": {
            "per_ticker_tokens": dict(token_usage or {}),
            "total_tokens": sum((token_usage or {}).values()),
        },
        "daily_api_cost_usd": daily_api_cost_usd,
    }


def make_dataset(
    *,
    tickers: Sequence[str] = ("AAPL", "MSFT"),
    window_days: int = 14,
    end: date = date(2026, 4, 28),
    daily_overrides: Mapping[str, Mapping[date, dict]] | None = None,
    logs: Sequence[PipelineEvent] = (),
    summary_overrides: Mapping[date, dict] | None = None,
    model_profile: str = "economy",
) -> AuditDataset:
    start = end - timedelta(days=window_days - 1)
    days = [start + timedelta(days=i) for i in range(window_days)]
    daily: dict[str, dict[date, dict]] = {}
    for t in tickers:
        per_day: dict[date, dict] = {}
        for d in days:
            override = (daily_overrides or {}).get(t, {}).get(d)
            per_day[d] = override or make_daily(ticker=t, as_of=d)
        daily[t] = per_day
    summaries: dict[date, dict] = {}
    for d in days:
        override = (summary_overrides or {}).get(d)
        summaries[d] = override or make_summary(d)
    return AuditDataset(
        window_start=start,
        window_end=end,
        tickers=tuple(tickers),
        daily=daily,
        logs=tuple(logs),
        summaries=summaries,
        model_profile=model_profile,
    )
