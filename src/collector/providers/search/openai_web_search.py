"""OpenAI-backed search evidence provider.

The provider is intentionally a small adapter around the Responses API so
collector code receives normalized `SearchEvidenceItem` records only.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from src.collector.search_evidence import SearchEvidenceItem


class OpenAIWebSearchProvider:
    def __init__(
        self,
        *,
        model: str,
        tool_type: str = "web_search",
        client: Any | None = None,
    ) -> None:
        self.model = str(model or "").strip() or "gpt-5.4"
        self.tool_type = str(tool_type or "").strip() or "web_search"
        self._client = client

    def search(self, *, ticker: str, queries: list[str], run_date: date) -> list[SearchEvidenceItem]:
        normalized_ticker = str(ticker or "").strip().upper()
        normalized_queries = [str(query).strip() for query in queries if str(query).strip()]
        if not normalized_ticker or not normalized_queries:
            return []

        response = self._client_or_default().responses.create(
            model=self.model,
            tools=[{"type": self.tool_type}],
            input=build_search_prompt(ticker=normalized_ticker, queries=normalized_queries, run_date=run_date),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "search_evidence",
                    "schema": search_evidence_schema(),
                    "strict": True,
                }
            },
        )
        payload = json.loads(_response_output_text(response))
        return _items_from_payload(payload, ticker=normalized_ticker, fallback_query=normalized_queries[0])

    def _client_or_default(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client


def build_search_prompt(*, ticker: str, queries: list[str], run_date: date) -> str:
    query_lines = "\n".join(f"- {query}" for query in queries)
    return (
        f"Find recent, source-backed public web evidence for ticker {ticker} as of {run_date.isoformat()}.\n"
        "Use the supplied queries and return concise evidence items only when a source URL is available.\n"
        "Prefer primary investor relations pages, SEC filings, reputable news, and company releases.\n"
        "Do not invent URLs, titles, dates, or metrics. If no source is found, return an empty items array.\n"
        f"Queries:\n{query_lines}"
    )


def search_evidence_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "published_at": {"type": "string"},
                        "snippet": {"type": "string"},
                        "evidence_type": {
                            "type": "string",
                            "enum": ["earnings", "filing", "news", "macro", "policy", "other"],
                        },
                        "relevance_score": {"type": "number"},
                        "freshness_hours": {"type": "integer"},
                    },
                    "required": [
                        "title",
                        "url",
                        "published_at",
                        "snippet",
                        "evidence_type",
                        "relevance_score",
                        "freshness_hours",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _response_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "")
    if output_text:
        return str(output_text)
    raise ValueError("OpenAI web search response did not include output_text")


def _items_from_payload(payload: Any, *, ticker: str, fallback_query: str) -> list[SearchEvidenceItem]:
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        return []
    items: list[SearchEvidenceItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        items.append(
            SearchEvidenceItem(
                ticker=ticker,
                query=fallback_query,
                title=str(raw.get("title") or "").strip(),
                url=url,
                published_at=str(raw.get("published_at") or "").strip(),
                snippet=str(raw.get("snippet") or "").strip(),
                evidence_type=str(raw.get("evidence_type") or "news").strip() or "news",
                relevance_score=_float(raw.get("relevance_score")),
                freshness_hours=_optional_int(raw.get("freshness_hours")),
            )
        )
    return items


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
