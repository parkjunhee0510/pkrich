from __future__ import annotations

import json
from typing import Any

from src.analyzer.base import AnalysisContext, ModuleResult, StructuredLLMModule
from src.analyzer.llm_runtime import parse_ticker_batch


class SignalTakeawayModule(StructuredLLMModule):
    name = "signal_takeaway_module"
    requires = {"summary", "trade_frame", "news_tone", "risks_or_watchpoints"}
    produces = {"signal_or_takeaway"}
    priority = 60

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        raise NotImplementedError("Use AnalysisOrchestrator for StructuredLLMModule execution")

    def build_batch_payload(self, ctx: AnalysisContext, batch_tickers: list[str]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for ticker in batch_tickers:
            upstream = ctx.intermediate_results.get(ticker, {})
            payloads.append(
                {
                    "ticker": ticker,
                    "summary": upstream.get("summary", ""),
                    "trade_frame": upstream.get("trade_frame", {}),
                    "news_tone": upstream.get("news_tone", {}),
                    "risks_or_watchpoints": upstream.get("risks_or_watchpoints", []),
                }
            )
        return payloads

    def build_system_prompt(self) -> str:
        return (
            "Return strict JSON with key 'tickers'. All human-readable output must be in Korean. "
            "signal_or_takeaway must be one structured sentence: "
            "\"[방향] — [핵심 catalyst] | 진입 트리거 [조건] | 목표 [가격1]/[가격2] | 손절 [가격]\"."
        )

    def build_user_prompt(self, batch_payload: list[dict[str, Any]], ctx: AnalysisContext) -> str:
        del ctx
        return (
            "각 티커에 대해 최종 시그널 한 줄을 작성하세요. 방향은 매수 관찰, 매수 유지, 중립 관찰, 중립 경계, 매도 경계 중 하나여야 합니다.\n\n"
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
                            "signal_or_takeaway": {"type": "string", "minLength": 30},
                        },
                        "required": ["ticker", "signal_or_takeaway"],
                    },
                }
            },
            "required": ["tickers"],
        }

    def response_schema_name(self) -> str:
        return "signal_takeaway_batch"

    def parse_batch_response(self, content: str, batch_tickers: list[str], ctx: AnalysisContext) -> dict[str, dict[str, Any]]:
        del ctx
        parsed = parse_ticker_batch(content, batch_tickers)
        return {
            entry["ticker"]: {"signal_or_takeaway": str(entry["signal_or_takeaway"])}
            for entry in parsed
        }

    def fallback_for_ticker(self, ticker: str, ctx: AnalysisContext) -> dict[str, Any]:
        fallback = ctx.fallback_payload_by_ticker[ticker]
        return {"signal_or_takeaway": fallback["signal_or_takeaway"]}
