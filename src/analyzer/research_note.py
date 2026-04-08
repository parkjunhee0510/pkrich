from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from src.types import CollectedTickerData, NewsItem, TickerAnalysis, WatchlistItem
from src.utils.env import load_dotenv


def analyze_tickers(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
) -> list[TickerAnalysis]:
    load_dotenv()
    if os.getenv("OPENAI_API_KEY"):
        llm_results = _analyze_with_openai(watchlist, collected, news_map, run_date)
        if llm_results:
            return llm_results
    return _build_fallback_analyses(watchlist, collected, news_map, run_date)


def _analyze_with_openai(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
) -> list[TickerAnalysis]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        payload = []
        for item in watchlist:
            market = collected[item.ticker]
            payload.append(
                {
                    "ticker": item.ticker,
                    "name": item.name,
                    "sector": item.sector,
                    "price": market.price,
                    "change_percent": market.change_percent,
                    "currency": market.currency,
                    "market_cap": market.market_cap,
                    "pe_ratio": market.pe_ratio,
                    "news": [
                        {
                            "title": article.title,
                            "source": article.source,
                            "published_at": article.published_at,
                        }
                        for article in news_map.get(item.ticker, [])
                    ],
                }
            )

        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You are a cost-aware equity research assistant. "
                                "Use only the provided data. Return strict JSON with key 'tickers'."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Create concise structured research notes for each ticker. "
                                "Required fields: ticker, summary, key_news, financial_highlights, "
                                "risks_or_watchpoints, signal_or_takeaway. "
                                f"Data date: {run_date.isoformat()}\n"
                                + json.dumps(payload, ensure_ascii=True)
                            ),
                        }
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ticker_research_batch",
                    "schema": _response_schema(),
                    "strict": True,
                }
            },
        )

        content = getattr(response, "output_text", "").strip()
        tickers = _parse_and_validate_response(content, watchlist)
        analyses: list[TickerAnalysis] = []
        for item in watchlist:
            match = next((entry for entry in tickers if entry["ticker"] == item.ticker), None)
            if not match:
                continue
            market = collected[item.ticker]
            analyses.append(
                TickerAnalysis(
                    ticker=item.ticker,
                    name=item.name,
                    date=run_date.isoformat(),
                    summary=match["summary"],
                    key_news=match["key_news"][:5],
                    financial_highlights=match["financial_highlights"][:5],
                    risks_or_watchpoints=match["risks_or_watchpoints"][:5],
                    signal_or_takeaway=match["signal_or_takeaway"],
                    data_snapshot=_build_snapshot(market),
                )
            )
        return analyses
    except Exception:
        return []


def _build_fallback_analyses(
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    run_date: date,
) -> list[TickerAnalysis]:
    analyses: list[TickerAnalysis] = []
    for item in watchlist:
        market = collected[item.ticker]
        ticker_news = news_map.get(item.ticker, [])
        price_text = f"{market.price:.2f} {market.currency}" if market.price is not None else "price unavailable"
        change_text = (
            f"{market.change_percent:+.2f}%"
            if market.change_percent is not None
            else "daily change unavailable"
        )
        analyses.append(
            TickerAnalysis(
                ticker=item.ticker,
                name=item.name,
                date=run_date.isoformat(),
                summary=(
                    f"{item.name} ({item.ticker}) is tracked in the {item.sector or 'unspecified'} sector. "
                    f"Latest observed price is {price_text} with {change_text}."
                ),
                key_news=[article.title for article in ticker_news[:5]],
                financial_highlights=[
                    f"Market cap: {market.market_cap}",
                    f"Trailing P/E: {market.pe_ratio}",
                    market.summary_note,
                ],
                risks_or_watchpoints=[
                    "Collected inputs may be incomplete if upstream data sources were unavailable.",
                    "Review the latest earnings date and major headlines before making decisions.",
                ],
                signal_or_takeaway="Maintain watchlist coverage and review for materially new developments.",
                data_snapshot=_build_snapshot(market),
            )
        )
    return analyses


def _build_snapshot(market: CollectedTickerData) -> dict[str, str]:
    return {
        "Price": f"{market.price:.2f} {market.currency}" if market.price is not None else "N/A",
        "Daily Change": f"{market.change_percent:+.2f}%" if market.change_percent is not None else "N/A",
        "Market Cap": market.market_cap,
        "Trailing P/E": market.pe_ratio,
        "Sector": market.sector or "N/A",
    }


def _parse_and_validate_response(
    content: str,
    watchlist: list[WatchlistItem],
) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object.")

    tickers = parsed.get("tickers")
    if not isinstance(tickers, list):
        raise ValueError("Model response must contain a 'tickers' list.")

    allowed_tickers = {item.ticker for item in watchlist}
    validated: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    for entry in tickers:
        if not isinstance(entry, dict):
            raise ValueError("Each ticker response must be an object.")

        ticker = _require_non_empty_string(entry, "ticker").upper()
        if ticker not in allowed_tickers:
            raise ValueError(f"Unexpected ticker in model response: {ticker}")
        if ticker in seen_tickers:
            raise ValueError(f"Duplicate ticker in model response: {ticker}")
        seen_tickers.add(ticker)

        validated.append(
            {
                "ticker": ticker,
                "summary": _require_non_empty_string(entry, "summary"),
                "key_news": _require_string_list(entry, "key_news"),
                "financial_highlights": _require_string_list(entry, "financial_highlights"),
                "risks_or_watchpoints": _require_string_list(entry, "risks_or_watchpoints"),
                "signal_or_takeaway": _require_non_empty_string(entry, "signal_or_takeaway"),
            }
        )

    return validated


def _require_non_empty_string(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field '{key}' must be a non-empty string.")
    return value.strip()


def _require_string_list(entry: dict[str, Any], key: str) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Field '{key}' must be a list.")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Field '{key}' must contain non-empty strings.")
        normalized.append(item.strip())
    return normalized


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "tickers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "ticker": {"type": "string"},
                        "summary": {"type": "string"},
                        "key_news": {"type": "array", "items": {"type": "string"}},
                        "financial_highlights": {"type": "array", "items": {"type": "string"}},
                        "risks_or_watchpoints": {"type": "array", "items": {"type": "string"}},
                        "signal_or_takeaway": {"type": "string"},
                    },
                    "required": [
                        "ticker",
                        "summary",
                        "key_news",
                        "financial_highlights",
                        "risks_or_watchpoints",
                        "signal_or_takeaway",
                    ],
                },
            }
        },
        "required": ["tickers"],
    }
