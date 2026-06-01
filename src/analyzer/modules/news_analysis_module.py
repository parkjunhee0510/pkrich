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
            "For each ticker, summarize up to 5 headlines and classify tone as bullish, neutral, or bearish. "
            "Strict grounding rule: every fact in your output must be directly supported by the input "
            "news.title or news.summary text. Do NOT introduce numbers, dates, names, deal sizes, "
            "executives, regulatory actions, or events that are not literally present in the input. "
            "If you cannot ground a claim, omit it or write '정보 부족'."
        )

    def build_user_prompt(self, batch_payload: list[dict[str, Any]], ctx: AnalysisContext) -> str:
        del ctx
        return (
            "각 티커에 대해 뉴스 헤드라인을 짧게 요약하고 전체 뉴스 톤을 분류하세요.\n"
            "key_news는 입력 뉴스 순서를 유지하고, 각 항목은 15단어 이하의 짧은 한국어 요약이어야 합니다.\n"
            "원문 영어 제목을 새로 쓰거나 의역한 영어 헤드라인을 만들지 마세요.\n"
            "영문 제목을 그대로 둘 경우 입력 title과 완전히 동일하게 복사하세요.\n"
            "news_tone.reasoning은 한 문장으로 쓰세요.\n\n"
            "[근거 강제 규칙 — 위반 시 환각으로 분류됨]\n"
            "- 각 key_news 항목은 입력 news 배열의 단일 헤드라인을 요약한 결과여야 합니다.\n"
            "- 입력 뉴스에 없는 숫자/날짜/인물/거래규모/규제조치/사건은 절대 추가하지 마세요.\n"
            "- 정보가 부족하면 해당 항목을 '정보 부족'으로 표기하거나 배열에서 제외하세요.\n"
            "- news_tone.reasoning은 key_news에 등장한 사실만 인용해야 하며 새 사실을 도입하지 마세요.\n"
            "- 톤 분류는 입력 헤드라인의 명시적 신호만 근거로 하고, 추론에 의한 외삽은 금지합니다.\n\n"
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
