from __future__ import annotations

import json
from typing import Any

from src.analyzer import research_note
from src.analyzer.base import AnalysisContext, ModuleResult, StructuredLLMModule
from src.analyzer.llm_runtime import parse_ticker_batch


class RiskAssessmentModule(StructuredLLMModule):
    name = "risk_assessment_module"
    requires = {"price", "fundamentals", "trade_frame", "news_tone"}
    produces = {"risks_or_watchpoints"}
    priority = 50

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
                    "trade_frame": upstream.get("trade_frame", {}),
                    "news_tone": upstream.get("news_tone", {}),
                    "options_summary": raw_payload.get("options_summary", {}),
                }
            )
        return payloads

    def build_system_prompt(self) -> str:
        return (
            "You identify measurable trading risks. Return strict JSON with key 'tickers'. "
            "All items must be in Korean and each risk must include a measurable trigger such as price, date, or threshold."
        )

    def build_user_prompt(self, batch_payload: list[dict[str, Any]], ctx: AnalysisContext) -> str:
        del ctx
        return (
            "각 티커에 대해 최대 4개의 리스크/체크포인트를 작성하세요. 모든 항목은 측정 가능한 트리거를 포함해야 합니다.\n\n"
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
                            "risks_or_watchpoints": {
                                "type": "array",
                                "items": {"type": "string", "minLength": 15},
                            },
                        },
                        "required": ["ticker", "risks_or_watchpoints"],
                    },
                }
            },
            "required": ["tickers"],
        }

    def response_schema_name(self) -> str:
        return "risk_assessment_batch"

    def parse_batch_response(self, content: str, batch_tickers: list[str], ctx: AnalysisContext) -> dict[str, dict[str, Any]]:
        del ctx
        parsed = parse_ticker_batch(content, batch_tickers)
        return {
            entry["ticker"]: {
                "risks_or_watchpoints": [str(item) for item in entry.get("risks_or_watchpoints", [])[:4]],
            }
            for entry in parsed
        }

    def fallback_for_ticker(self, ticker: str, ctx: AnalysisContext) -> dict[str, Any]:
        fallback = ctx.fallback_payload_by_ticker[ticker]
        return {"risks_or_watchpoints": fallback["risks_or_watchpoints"]}
