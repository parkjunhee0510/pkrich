from __future__ import annotations

import json
from typing import Any

from src.analyzer import research_note
from src.analyzer.base import AnalysisContext, ModuleResult, StructuredLLMModule
from src.analyzer.llm_runtime import parse_ticker_batch
from src.utils.macro_event_match import match_macro_events_for_context


class ResearchNarrativeModule(StructuredLLMModule):
    name = "research_narrative_module"
    requires = {"price", "fundamentals", "news_tone", "valuation_score", "trade_frame", "peer_rank"}
    produces = {"summary", "financial_highlights"}
    priority = 40

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        raise NotImplementedError("Use AnalysisOrchestrator for StructuredLLMModule execution")

    def build_batch_payload(self, ctx: AnalysisContext, batch_tickers: list[str]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for ticker in batch_tickers:
            raw_payload = ctx.raw_payload_by_ticker[ticker]
            upstream = ctx.intermediate_results.get(ticker, {})
            payloads.append(
                {
                    "ticker": ticker,
                    "context": research_note._build_ticker_context(raw_payload),
                    "valuation_score": upstream.get("valuation_score", {}),
                    "trade_frame": upstream.get("trade_frame", {}),
                    "news_tone": upstream.get("news_tone", {}),
                    "peer_rank": upstream.get("peer_rank", {}),
                    "macro_event_summary": _compact_macro_event_summary(raw_payload, ctx.macro_context),
                }
            )
        return payloads

    def build_system_prompt(self) -> str:
        return (
            "You are a professional equity research analyst. Return strict JSON with key 'tickers'. "
            "All human-readable output must be in Korean. "
            "summary must be exactly 2 sentences. financial_highlights must be short, concrete, and numeric when possible."
        )

    def build_user_prompt(self, batch_payload: list[dict[str, Any]], ctx: AnalysisContext) -> str:
        del ctx
        return (
            "각 티커에 대해 2문장 요약과 핵심 재무 하이라이트를 작성하세요.\n"
            "summary는 현재 상황과 다음 촉매를 분리해 2문장으로 쓰고, financial_highlights는 최대 5개입니다.\n\n"
            f"{json.dumps(batch_payload, ensure_ascii=True)}"
        )

    def response_schema(self) -> dict[str, Any]:
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
                            "summary": {"type": "string", "minLength": 40},
                            "financial_highlights": {
                                "type": "array",
                                "items": {"type": "string", "minLength": 15},
                            },
                        },
                        "required": ["ticker", "summary", "financial_highlights"],
                    },
                }
            },
            "required": ["tickers"],
        }

    def response_schema_name(self) -> str:
        return "research_narrative_batch"

    def parse_batch_response(self, content: str, batch_tickers: list[str], ctx: AnalysisContext) -> dict[str, dict[str, Any]]:
        del ctx
        parsed = parse_ticker_batch(content, batch_tickers)
        return {
            entry["ticker"]: {
                "summary": str(entry["summary"]),
                "financial_highlights": [str(item) for item in entry.get("financial_highlights", [])[:5]],
            }
            for entry in parsed
        }

    def fallback_for_ticker(self, ticker: str, ctx: AnalysisContext) -> dict[str, Any]:
        fallback = ctx.fallback_payload_by_ticker[ticker]
        return {
            "summary": fallback["summary"],
            "financial_highlights": fallback["financial_highlights"],
        }


def _compact_macro_event_summary(
    raw_payload: dict[str, Any],
    macro_context: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(macro_context, dict):
        return []
    matched_events = match_macro_events_for_context(
        macro_context,
        sector=str(raw_payload.get("sector", "")),
        industry=str(raw_payload.get("industry", "")),
        keywords=[str(item) for item in raw_payload.get("keywords", []) if str(item).strip()],
    )
    summaries: list[str] = []
    for event in matched_events[:2]:
        score = int(event.get("score", 0) or 0)
        matched_dimension = str(event.get("matched_dimension", ""))
        if abs(score) < 3 and matched_dimension != "industry":
            continue
        summary = str(event.get("summary_ko", "")).strip()
        severity = str(event.get("severity", "")).strip()
        if summary:
            summaries.append(f"{severity}: {summary}" if severity else summary)
    return summaries
