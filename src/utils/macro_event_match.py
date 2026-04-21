from __future__ import annotations

from typing import Any

_SECTOR_ALIASES = {
    "consumer staples": "consumer defensive",
    "consumer discretionary": "consumer cyclical",
    "communication": "communication services",
    "financials": "financial",
}

_EVENT_SECTOR_IMPACTS: dict[str, dict[str, int]] = {
    "hormuz_disruption": {
        "energy": 5,
        "utilities": 1,
        "industrials": -3,
        "consumer cyclical": -4,
        "technology": -2,
        "communication services": -2,
    },
    "middle_east_escalation": {
        "energy": 3,
        "utilities": 1,
        "healthcare": 1,
        "consumer defensive": 1,
        "technology": -2,
        "communication services": -2,
        "consumer cyclical": -3,
        "financial": -2,
        "industrials": -1,
    },
    "opec_supply_shock": {
        "energy": 4,
        "utilities": 1,
        "industrials": -2,
        "consumer cyclical": -4,
        "technology": -1,
    },
    "shipping_disruption": {
        "industrials": -2,
        "materials": -2,
        "consumer cyclical": -2,
        "technology": -1,
        "consumer defensive": -1,
        "energy": 1,
    },
    "sanctions_escalation": {
        "materials": 1,
        "energy": 2,
        "technology": -2,
        "industrials": -2,
        "financial": -1,
        "consumer cyclical": -1,
    },
}

_EVENT_INDUSTRY_RULES: dict[str, list[tuple[tuple[str, ...], int, str]]] = {
    "hormuz_disruption": [
        (("airline", "airlines", "air freight", "travel"), -6, "유가 급등 시 항공·여행 업종 원가 부담이 큽니다."),
        (("cruise", "hotel", "lodging", "resort"), -5, "유가와 여행 심리 부담이 크루즈·호텔 업종에 직접 역풍입니다."),
        (("shipping", "marine", "freight", "logistics", "container"), -5, "해상 운송 차질이 해운·물류 업종에 직접 부담입니다."),
        (("rail", "railroad", "trucking", "truck", "freight rail"), -4, "연료비와 운송 경로 부담이 철도·트럭킹 업종에 불리합니다."),
        (("defense", "aerospace", "weapons"), 2, "지정학 긴장은 방산 수요 기대를 자극할 수 있습니다."),
        (("oil", "exploration", "e&p", "refining", "midstream"), 5, "원유 공급 차질은 에너지 밸류체인에 우호적일 수 있습니다."),
    ],
    "middle_east_escalation": [
        (("defense", "aerospace", "weapons"), 5, "중동 확전 우려는 방산 수요 기대를 높일 수 있습니다."),
        (("airline", "airlines", "travel", "leisure"), -4, "중동 확전은 항공·여행 수요와 원가 측면에서 부담입니다."),
        (("cruise", "hotel", "lodging", "resort"), -4, "여행 심리 약화가 크루즈·호텔 업종에 부담입니다."),
        (("shipping", "marine", "logistics"), -4, "분쟁 확전은 해상 운송 경로와 보험 비용에 부담입니다."),
        (("rail", "railroad", "trucking", "truck"), -2, "운송 전반의 연료·물류 비용 부담이 커질 수 있습니다."),
        (("oil", "exploration", "e&p", "refining", "midstream"), 3, "에너지 공급 차질 우려가 커질 수 있습니다."),
    ],
    "opec_supply_shock": [
        (("airline", "airlines", "travel"), -5, "OPEC 공급 충격은 항공 연료비 부담을 키웁니다."),
        (("cruise", "hotel", "lodging", "resort"), -3, "여행 관련 업종은 에너지 비용과 수요 둔화 부담을 함께 받습니다."),
        (("trucking", "rail", "logistics", "shipping"), -4, "운송 업종은 연료비와 해상 운임 압박을 받기 쉽습니다."),
        (("oil", "exploration", "e&p", "refining", "midstream"), 4, "에너지 가격 상승은 상류 에너지 업종에 우호적일 수 있습니다."),
    ],
    "shipping_disruption": [
        (("shipping", "marine", "container", "freight"), -6, "해운 차질은 해운·물류 업종의 운영 변동성을 키웁니다."),
        (("retail", "consumer electronics", "hardware", "semiconductor"), -3, "공급망 차질이 부품·재고 흐름에 부담입니다."),
        (("semiconductor equipment", "wafer fab", "chip equipment", "lithography"), -4, "장비 리드타임과 글로벌 부품 조달 차질이 반도체 장비 업종에 부담입니다."),
        (("rail", "railroad", "trucking", "truck", "logistics"), -3, "항만 병목이 철도·트럭킹 연계 물류 흐름에 부담을 줍니다."),
        (("cruise", "hotel", "lodging"), -2, "여행 수요 둔화와 운임 부담이 간접 악재로 작용할 수 있습니다."),
        (("defense", "aerospace"), 1, "직접 수혜는 제한적이지만 지정학 프리미엄은 일부 존재합니다."),
    ],
    "sanctions_escalation": [
        (("semiconductor", "chip", "electronics", "hardware"), -5, "제재·수출통제는 반도체·전자 밸류체인에 직접 부담입니다."),
        (("semiconductor equipment", "wafer fab", "chip equipment", "lithography"), -6, "수출통제 강화는 반도체 장비 업종의 해외 매출과 공급망에 직접 부담입니다."),
        (("defense", "aerospace"), 2, "제재 강화는 방산 예산 기대를 일부 지지할 수 있습니다."),
        (("shipping", "marine", "logistics"), -2, "제재 강화는 물류 경로와 규제 비용을 높일 수 있습니다."),
        (("rail", "railroad", "trucking", "truck"), -1, "국제 제재로 물류 흐름이 꼬이면 철도·트럭킹 업종에도 간접 부담입니다."),
    ],
}


def match_macro_events_for_context(
    macro_context: dict[str, Any] | None,
    *,
    sector: str,
    industry: str = "",
    keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(macro_context, dict):
        return []
    events = macro_context.get("macro_events", [])
    if not isinstance(events, list):
        return []

    matches: list[dict[str, Any]] = []
    for event in events[:3]:
        if not isinstance(event, dict):
            continue
        impact = score_macro_event_match(
            event,
            sector=sector,
            industry=industry,
            keywords=keywords or [],
        )
        if impact["score"] == 0:
            continue
        matches.append({**event, **impact})
    matches.sort(key=lambda item: abs(int(item.get("score", 0))), reverse=True)
    return matches


def score_macro_event_match(
    event: dict[str, Any],
    *,
    sector: str,
    industry: str = "",
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    normalized_sector = normalize_sector(sector)
    industry_text = normalize_text(industry)
    keyword_text = " ".join(normalize_text(keyword) for keyword in (keywords or []))
    combined_text = f"{industry_text} {keyword_text}".strip()
    event_type = str(event.get("event_type", "")).strip()

    score = _EVENT_SECTOR_IMPACTS.get(event_type, {}).get(normalized_sector, 0)
    matched_dimension = "sector" if score else ""
    reason = str(event.get("summary_ko", "")).strip()

    for tokens, candidate_score, candidate_reason in _EVENT_INDUSTRY_RULES.get(event_type, []):
        if not any(token in combined_text for token in tokens):
            continue
        if abs(candidate_score) >= abs(score):
            score = candidate_score
            matched_dimension = "industry"
            reason = candidate_reason

    return {
        "score": int(score),
        "matched_dimension": matched_dimension or "none",
        "match_reason": reason,
    }


def normalize_sector(raw: str) -> str:
    normalized = normalize_text(raw)
    return _SECTOR_ALIASES.get(normalized, normalized)


def normalize_text(raw: str) -> str:
    return " ".join(str(raw or "").strip().lower().split())
