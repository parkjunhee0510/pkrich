from __future__ import annotations

from src.analyzer.prompts.base import PromptTemplate

_NEWS_SCHEMA = {
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

_NARRATIVE_SCHEMA = {
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

_RISK_SCHEMA = {
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

_SIGNAL_SCHEMA = {
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

_WEEKLY_REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string", "minLength": 10},
        "summary": {"type": "string", "minLength": 20},
        "market_environment": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string", "minLength": 10},
                "details": {"type": "array", "items": {"type": "string", "minLength": 5}},
            },
            "required": ["summary", "details"],
        },
        "top_movers": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string", "minLength": 10},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "ticker": {"type": "string"},
                            "name": {"type": "string"},
                            "weekly_change": {"type": "string"},
                            "catalyst": {"type": "string", "minLength": 3},
                            "decision_change": {"type": "string", "minLength": 3},
                        },
                        "required": ["ticker", "name", "weekly_change", "catalyst", "decision_change"],
                    },
                },
            },
            "required": ["summary", "items"],
        },
        "signal_review": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string", "minLength": 10},
                "details": {"type": "array", "items": {"type": "string", "minLength": 5}},
            },
            "required": ["summary", "details"],
        },
        "risk_points": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string", "minLength": 10},
                "items": {"type": "array", "items": {"type": "string", "minLength": 5}},
            },
            "required": ["summary", "items"],
        },
        "next_week_action_plan": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string", "minLength": 10},
                "items": {"type": "array", "items": {"type": "string", "minLength": 5}},
            },
            "required": ["summary", "items"],
        },
        "portfolio_suggestions": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string", "minLength": 10},
                "items": {"type": "array", "items": {"type": "string", "minLength": 5}},
            },
            "required": ["summary", "items"],
        },
    },
    "required": [
        "headline",
        "summary",
        "market_environment",
        "top_movers",
        "signal_review",
        "risk_points",
        "next_week_action_plan",
        "portfolio_suggestions",
    ],
}

PROMPT_SET = {
    "news_analysis_module": PromptTemplate(
        name="news_analysis_module",
        version="research_v1",
        system_template=(
            "You are a market news analyst. Return strict JSON with key 'tickers'. "
            "All human-readable fields must be in Korean. "
            "For each ticker, summarize up to 5 headlines and classify tone as bullish, neutral, or bearish."
        ),
        user_template=(
            "각 티커의 뉴스 헤드라인을 짧게 요약하고 전체 뉴스 톤을 분류해주세요.\n"
            "key_news는 입력 뉴스 순서를 최대한 유지하고, 각 항목은 15단어 이하의 짧은 한국어 요약으로 작성합니다.\n"
            "news_tone.reasoning은 한 문장으로 작성합니다.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_NEWS_SCHEMA,
    ),
    "research_narrative_module": PromptTemplate(
        name="research_narrative_module",
        version="research_v1",
        system_template=(
            "You are a professional equity research analyst. Return strict JSON with key 'tickers'. "
            "All human-readable output must be in Korean. "
            "summary must be exactly 2 sentences. financial_highlights must be short, concrete, and numeric when possible."
        ),
        user_template=(
            "각 티커에 대해 2문장 요약과 핵심 재무 하이라이트를 작성해주세요.\n"
            "summary는 현재 상황과 다음 촉매를 분리한 2문장으로 쓰고, financial_highlights는 최대 5개입니다.\n"
            "peer_rank가 주어지면 PER 하위 구간과 RS 상위 구간 같은 정량 비교를 짧게 반영할 수 있지만, 숫자 gap이 없으면 과장하지 마세요.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_NARRATIVE_SCHEMA,
    ),
    "risk_assessment_module": PromptTemplate(
        name="risk_assessment_module",
        version="research_v1",
        system_template=(
            "You identify measurable trading risks. Return strict JSON with key 'tickers'. "
            "All items must be in Korean and each risk must include a measurable trigger such as price, date, or threshold."
        ),
        user_template=(
            "각 티커에 대해 최대 4개의 리스크 체크포인트를 작성해주세요. 모든 항목은 측정 가능한 트리거를 포함해야 합니다.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_RISK_SCHEMA,
    ),
    "signal_takeaway_module": PromptTemplate(
        name="signal_takeaway_module",
        version="research_v1",
        system_template=(
            "Return strict JSON with key 'tickers'. All human-readable output must be in Korean. "
            "signal_or_takeaway must be one structured sentence: "
            "\"[방향] — [핵심 catalyst] | 진입 트리거 [조건] | 목표 [가격]/[가격] | 손절 [가격]\"."
        ),
        user_template=(
            "각 티커에 대해 최종 시그널 한 줄을 작성해주세요. 방향은 매수 관찰, 매수 우선, 중립 관찰, 중립 경계, 매도 경계 중 하나여야 합니다.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_SIGNAL_SCHEMA,
    ),
    "weekly_insight_module": PromptTemplate(
        name="weekly_insight_module",
        version="research_v1",
        system_template=(
            "You are a weekly market strategist. Return strict JSON only. "
            "All human-readable output must be in Korean. "
            "Write a structured weekly report with exactly the requested keys and no markdown."
        ),
        user_template=(
            "주간 집계 데이터를 바탕으로 구조화된 주간 보고서를 작성해주세요.\n"
            "각 섹션은 과장 없이 숫자와 이벤트를 근거로 요약하고, 데이터가 부족하면 그 사실을 짧게 명시해주세요.\n"
            "top_movers.items는 최대 3개만 유지하고, portfolio_suggestions와 next_week_action_plan은 실행 가능한 문장 위주로 작성해주세요.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_WEEKLY_REPORT_SCHEMA,
    ),
}
