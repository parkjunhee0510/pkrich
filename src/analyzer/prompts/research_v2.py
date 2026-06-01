from __future__ import annotations

from src.analyzer.prompts.base import PromptTemplate
from src.analyzer.prompts.research_v1 import (
    _ANTI_HALLUCINATION_SYSTEM_RULE,
    _ANTI_HALLUCINATION_USER_RULE,
    _NARRATIVE_SCHEMA,
    _NEWS_SCHEMA,
    _RISK_SCHEMA,
    _SIGNAL_SCHEMA,
    _WEEKLY_REPORT_SCHEMA,
)

PROMPT_SET = {
    "news_analysis_module": PromptTemplate(
        name="news_analysis_module",
        version="research_v2",
        system_template=(
            "You are a catalyst-focused equity news analyst. Return strict JSON with key 'tickers'. "
            "All human-readable fields must be in Korean. Prefer concise, trader-relevant phrasing over generic summaries. "
            + _ANTI_HALLUCINATION_SYSTEM_RULE
        ),
        user_template=(
            "각 티커의 헤드라인을 촉매 우선순위로 짧게 요약하고 전체 뉴스 톤을 분류해주세요.\n"
            "중복 이벤트는 반복 설명하지 말고, key_news는 최대 5개로 유지해주세요.\n\n"
            "영문 헤드라인을 재작성해 새 영어 제목처럼 만들지 마세요. 영어로 보존해야 하면 입력 title을 그대로 복사하고, 그 외에는 한국어로 요약하세요.\n\n"
            + _ANTI_HALLUCINATION_USER_RULE
            + "\n"
            "{batch_payload_json}"
        ),
        output_schema=_NEWS_SCHEMA,
    ),
    "research_narrative_module": PromptTemplate(
        name="research_narrative_module",
        version="research_v2",
        system_template=(
            "You are a trading-oriented equity research analyst. Return strict JSON with key 'tickers'. "
            "All human-readable output must be in Korean. summary must be exactly 2 sentences with price context and catalyst timing. "
            + _ANTI_HALLUCINATION_SYSTEM_RULE
        ),
        user_template=(
            "각 티커에 대해 트레이딩 관점의 2문장 요약과 정량 중심 financial_highlights를 작성해주세요.\n"
            "summary는 가격 맥락과 다음 촉매를 모두 포함해야 하고, highlights는 숫자 중심으로 작성해주세요.\n"
            "peer_rank가 주어지면 PER/RS/ROE percentile을 짧게 활용할 수 있지만, percentile만으로 과장된 결론을 만들지 마세요.\n\n"
            "macro_event_summary가 주어지면 업종 전이 경로가 분명한 거시 충격만 1문장 안에서 짧게 반영하고, 공포감을 과장하지 마세요.\n\n"
            + _ANTI_HALLUCINATION_USER_RULE
            + "financial_highlights의 숫자는 payload에 있는 값만 그대로 사용하고, 새 비율이나 가격을 계산하지 마세요.\n"
            + "금지 예시: 입력에 없는 실적일, 계약, 경영진 이름, 목표가를 단정적으로 쓰지 마세요.\n"
            "모범 예시: 확인되지 않은 슬롯은 '—' 또는 'N/A'로 두고, 검증 가능한 수치만 서술하세요.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_NARRATIVE_SCHEMA,
    ),
    "risk_assessment_module": PromptTemplate(
        name="risk_assessment_module",
        version="research_v2",
        system_template=(
            "You identify measurable trading risks and invalidation triggers. Return strict JSON with key 'tickers'. "
            "All items must be in Korean and actionable. "
            + _ANTI_HALLUCINATION_SYSTEM_RULE
        ),
        user_template=(
            "각 티커에 대해 측정 가능한 리스크와 감시 사인을 최대 4개 작성해주세요. 가격, 날짜, 수치 임계값 중 하나를 반드시 포함해주세요.\n\n"
            + _ANTI_HALLUCINATION_USER_RULE
            + "가격/날짜/수치 트리거는 payload에 있는 값만 사용하고, 새 트리거 값을 계산하거나 반올림해 만들지 마세요.\n"
            + "\n"
            "{batch_payload_json}"
        ),
        output_schema=_RISK_SCHEMA,
    ),
    "signal_takeaway_module": PromptTemplate(
        name="signal_takeaway_module",
        version="research_v2",
        system_template=(
            "Return strict JSON with key 'tickers'. All human-readable output must be in Korean. "
            "signal_or_takeaway MUST be exactly one sentence matching the shape "
            "\"[방향] — [핵심 catalyst] | 진입 트리거 [조건] | 목표 [가격1]/[가격2] | 손절 [가격]\". "
            "방향은 반드시 '매수 관찰|매수 유지|매수 우선|중립 관찰|중립 경계|매도 경계|매도 관찰|매도 유지|매도' 중 하나여야 합니다. "
            "매수 시 목표가는 오름차순(가격1 < 가격2), 매도 시 내림차순이어야 하며 손절은 진입 반대편에 위치해야 합니다. "
            "'진입트리거:', '목표가:', '손절가:' 같은 콜론 포맷이나 '/' 구분자는 금지하고 반드시 ' | ' 구분자와 '—'(em-dash)를 사용합니다. "
            + _ANTI_HALLUCINATION_SYSTEM_RULE + " "
            "좋은 예시: "
            "\"매수 관찰 — 실적 D-7 강세 모멘텀 | 진입 트리거 273 상향 돌파 | 목표 282/297달러 | 손절 260달러\". "
            "\"매도 경계 — 가이던스 하향과 약한 수급 | 진입 트리거 88 이탈 확인 | 목표 82/76달러 | 손절 92달러\". "
            "\"중립 관찰 — 이벤트 대기와 박스권 지속 | 진입 트리거 145 돌파 확인 | 목표 152/158달러 | 손절 139달러\". "
            "금지 예시: "
            "\"진입트리거: 273 / 목표가: 282, 297 / 손절가: 260\". "
            "\"매수 관찰 — x | 목표 835/759 | 손절 733\". "
            "\"매수 우선 — 5월 3일 CEO 간담회 기대 | 진입 트리거 301 돌파 | 목표 325/340달러 | 손절 289달러\" (입력에 없는 이벤트/인물명 금지). "
            "\"매도 경계 — 신규 대형 계약 실망 | 진입 트리거 210 이탈 | 목표 198/190달러 | 손절 218달러\" (입력에 없는 계약 금지)."
        ),
        user_template=(
            "각 티커에 대해 최종 시그널 한 줄을 작성해주세요. 진입 트리거, 목표가, 손절가가 빠지면 안 됩니다.\n\n"
            + _ANTI_HALLUCINATION_USER_RULE
            + "payload 안의 must_use_values는 반드시 따라야 하는 화이트리스트입니다.\n"
            + "매수/중립 방향의 목표는 must_use_values.resistance_levels에서만, 손절은 must_use_values.support_levels에서만 선택하세요.\n"
            + "매도 방향의 목표는 must_use_values.support_levels에서만, 손절은 must_use_values.resistance_levels에서만 선택하세요.\n"
            + "사용 가능한 값이 없으면 목표 N/A/N/A 또는 손절 N/A를 쓰고 새 가격을 만들지 마세요.\n"
            + "must_use_values에 없는 가격, 이벤트 날짜, 기술적 레벨은 추측하거나 새로 만들지 마세요.\n"
            + "근거 없는 값은 반드시 '—' 또는 'N/A'로 두고, 추측으로 채우지 마세요.\n\n"
            "{batch_payload_json}"
        ),
        output_schema=_SIGNAL_SCHEMA,
    ),
    "weekly_insight_module": PromptTemplate(
        name="weekly_insight_module",
        version="research_v2",
        system_template=(
            "You are a PM-style weekly strategy analyst. Return strict JSON only. "
            "All human-readable output must be in Korean and concise but actionable. "
            + _ANTI_HALLUCINATION_SYSTEM_RULE
        ),
        user_template=(
            "주간 집계 데이터를 기반으로 다음 주 의사결정에 바로 쓸 수 있는 구조화 보고서를 작성해주세요.\n"
            "시장 환경, 핵심 이동 종목, 시그널 성과, 리스크, 액션 플랜, 포트폴리오 제안을 모두 채우되 숫자와 일정 중심으로 요약해주세요.\n"
            "불확실하면 단정하지 말고 데이터 부족을 명확히 적어주세요.\n\n"
            + _ANTI_HALLUCINATION_USER_RULE
            + "\n"
            "{batch_payload_json}"
        ),
        output_schema=_WEEKLY_REPORT_SCHEMA,
    ),
}
