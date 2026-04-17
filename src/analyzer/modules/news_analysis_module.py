from __future__ import annotations

import json
from typing import Any

from src.analyzer import research_note
from src.analyzer.base import AnalysisContext, ModuleResult, StructuredLLMModule
from src.analyzer.llm_runtime import parse_ticker_batch


class NewsAnalysisModule(StructuredLLMModule):
    name = "news_analysis_module"
    requires = {"news", "price", "upcoming_events"}
    produces = {"news_tone", "key_news"}
    priority = 30

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        raise NotImplementedError("Use AnalysisOrchestrator for StructuredLLMModule execution")

    def build_batch_payload(self, ctx: AnalysisContext, batch_tickers: list[str]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for ticker in batch_tickers:
            raw_payload = ctx.raw_payload_by_ticker[ticker]
            payloads.append(
                {
                    "ticker": ticker,
                    "context": research_note._build_ticker_context(raw_payload),
                    "news": raw_payload.get("news", [])[:5],
                    "upcoming_events": raw_payload.get("upcoming_events", [])[:3],
                }
            )
        return payloads

    def build_system_prompt(self) -> str:
        return (
            "You are a market news analyst. Return strict JSON with key 'tickers'. "
            "All human-readable fields must be in Korean. "
            "For each ticker, summarize up to 5 headlines and classify tone as bullish, neutral, or bearish."
        )

    def build_user_prompt(self, batch_payload: list[dict[str, Any]], ctx: AnalysisContext) -> str:
        del ctx
        return (
            "각 티커에 대해 뉴스 헤드라인을 짧게 요약하고 전체 뉴스 톤을 분류하세요.\n"
            "key_news는 입력 뉴스 순서를 유지하고, 각 항목은 15단어 이하의 짧은 한국어 요약이어야 합니다.\n"
            "news_tone.reasoning은 한 문장으로 쓰세요.\n\n"
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
                            "key_news": {"type": "array", "items": {"type": "string"}},
                            "news_tone": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {"type": "string"},
                                    "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
                                    "reasoning": {"type": "string", "minLength": 10},
                                },
                                "required": ["label", "confidence", "reasoning"],
                            },
                        },
                        "required": ["ticker", "key_news", "news_tone"],
                    },
                }
            },
            "required": ["tickers"],
        }

    def response_schema_name(self) -> str:
        return "news_analysis_batch"

    def parse_batch_response(self, content: str, batch_tickers: list[str], ctx: AnalysisContext) -> dict[str, dict[str, Any]]:
        del ctx
        parsed = parse_ticker_batch(content, batch_tickers)
        results: dict[str, dict[str, Any]] = {}
        for entry in parsed:
            results[entry["ticker"]] = {
                "key_news": [str(item) for item in entry.get("key_news", [])[:5]],
                "news_tone": entry["news_tone"],
            }
        return results

    def fallback_for_ticker(self, ticker: str, ctx: AnalysisContext) -> dict[str, Any]:
        raw_payload = ctx.raw_payload_by_ticker[ticker]
        headlines = [str(item.get("title", "")) for item in raw_payload.get("news", [])[:5]]
        lowered = " ".join(headlines).lower()
        label = "neutral"
        confidence = 2
        if any(keyword in lowered for keyword in ["beat", "upgrade", "buyback", "guidance raise", "surge"]):
            label = "bullish"
            confidence = 3
        elif any(keyword in lowered for keyword in ["miss", "downgrade", "lawsuit", "cut", "drop"]):
            label = "bearish"
            confidence = 3
        return {
            "key_news": headlines[:5],
            "news_tone": {
                "label": label,
                "confidence": confidence,
                "reasoning": "헤드라인 기반의 보수적 톤 분류입니다.",
            },
        }
