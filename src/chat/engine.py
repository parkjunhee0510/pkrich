from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def answer_question(question: str, *, output_root: Path | None = None) -> dict[str, Any]:
    root = output_root or Path("output")
    dashboard = _load_json(root / "data" / "dashboard.json", default={"days": []})
    days = dashboard.get("days", [])
    latest_day = days[-1] if days else {}
    tickers = latest_day.get("tickers", [])
    normalized_question = question.strip()
    if not normalized_question:
        return {
            "answer": "질문이 비어 있습니다.",
            "matched_tickers": [],
            "sources": [],
        }

    matched_tickers = _find_relevant_tickers(normalized_question, tickers)
    context = _build_context(matched_tickers)
    llm_answer = _answer_with_openai(normalized_question, context)
    if llm_answer:
        return {
            "answer": llm_answer,
            "matched_tickers": [ticker.get("ticker", "") for ticker in matched_tickers],
            "sources": _build_sources(matched_tickers),
        }

    return {
        "answer": _build_fallback_answer(normalized_question, matched_tickers),
        "matched_tickers": [ticker.get("ticker", "") for ticker in matched_tickers],
        "sources": _build_sources(matched_tickers),
    }


def _load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _find_relevant_tickers(question: str, tickers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = question.lower()
    matched = [
        ticker for ticker in tickers
        if str(ticker.get("ticker", "")).lower() in normalized
        or str(ticker.get("name", "")).lower() in normalized
    ]
    if matched:
        return matched[:3]
    return tickers[:2]


def _build_context(tickers: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for ticker in tickers[:3]:
        chunks.append(
            "\n".join(
                [
                    f"Ticker: {ticker.get('ticker', 'N/A')} / {ticker.get('name', 'N/A')}",
                    f"Summary: {ticker.get('summary', 'N/A')}",
                    f"Signal: {ticker.get('signal_or_takeaway', 'N/A')}",
                    f"News tone: {ticker.get('news_tone', {}).get('label', 'N/A')}",
                    f"Top news: {'; '.join(ticker.get('key_news', [])[:3]) or 'N/A'}",
                ]
            )
        )
    return "\n\n".join(chunks)


def _answer_with_openai(question: str, context: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not context:
        return ""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            input=[
                {
                    "role": "system",
                    "content": "Answer in Korean. Use only the provided stock research context. Be concise and cite ticker symbols.",
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nContext:\n{context}",
                },
            ],
        )
        return getattr(response, "output_text", "").strip()
    except Exception:
        return ""


def _build_fallback_answer(question: str, tickers: list[dict[str, Any]]) -> str:
    if not tickers:
        return f"현재 저장된 리서치 데이터에서 '{question}'와 관련된 종목을 찾지 못했습니다."
    lead = tickers[0]
    summary = str(lead.get("summary", "")).strip() or "요약 데이터가 없습니다."
    signal = str(lead.get("signal_or_takeaway", "")).strip() or "시그널 데이터가 없습니다."
    return f"{lead.get('ticker', 'N/A')} 기준 요약은 다음과 같습니다. {summary} 한줄 판단은 {signal} 입니다."


def _build_sources(tickers: list[dict[str, Any]]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for ticker in tickers:
        for ref in ticker.get("news_references", [])[:3]:
            if not isinstance(ref, dict):
                continue
            sources.append(
                {
                    "ticker": str(ticker.get("ticker", "")),
                    "title": str(ref.get("title", "")),
                    "link": str(ref.get("link", "")),
                }
            )
    return sources[:5]
