from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.types import TickerDecision

SWAP_ACTION_PENALTY = 10
EVENT_BASE_URGENCY = 60
EVENT_MAX_DAYS_WINDOW = 30
EVENT_CONVICTION_BASELINE = 70
INVALID_DAYS_UNTIL = EVENT_MAX_DAYS_WINDOW + 365
EVENT_LABEL_TRANSLATIONS = {
    "earnings": "실적 발표",
    "earnings call": "실적 발표",
    "dividend payment date": "배당 지급일",
    "ex-dividend date": "배당락일",
    "fed meeting": "연준 회의",
    "fomc meeting": "연준 회의",
    "cpi release": "CPI 발표",
    "developer conference": "개발자 컨퍼런스",
    "product launch": "신제품 출시",
    "shareholder meeting": "주주총회",
}


def build_pm_view(
    analyses: Sequence[Any],
    *,
    as_of: str,
    portfolio_summary: Any | None,
    portfolio_risk: dict[str, Any] | None,
    decision_map: Mapping[str, TickerDecision],
) -> dict[str, Any]:
    risk = portfolio_risk if isinstance(portfolio_risk, dict) else {}
    held_tickers = _held_tickers(portfolio_summary)
    held_analyses = [analysis for analysis in analyses if getattr(analysis, "ticker", "") in held_tickers]
    candidate_analyses = [analysis for analysis in analyses if getattr(analysis, "ticker", "") not in held_tickers]

    swap_candidates = _build_swap_candidates(held_analyses, candidate_analyses, risk, decision_map)
    event_exposure_items = _build_event_exposure_items(held_analyses, risk, decision_map)
    today_priority_queue = _build_today_priority_queue(swap_candidates, event_exposure_items, risk)

    empty_states = {
        "swap_candidates": _swap_empty_state(held_tickers, swap_candidates),
        "event_exposure_items": _event_empty_state(held_tickers, event_exposure_items),
        "today_priority_queue": _queue_empty_state(held_tickers, today_priority_queue),
    }
    return {
        "as_of": as_of,
        "swap_candidates": swap_candidates,
        "event_exposure_items": event_exposure_items,
        "today_priority_queue": today_priority_queue,
        "empty_states": empty_states,
    }


def _build_swap_candidates(
    held_analyses: Sequence[Any],
    candidate_analyses: Sequence[Any],
    portfolio_risk: dict[str, Any],
    decision_map: Mapping[str, TickerDecision],
) -> list[dict[str, Any]]:
    weights = _positions_by_weight(portfolio_risk)
    candidates: list[dict[str, Any]] = []
    for held in held_analyses:
        held_sector = _sector(held)
        held_decision = _decision_for(held, decision_map)
        if held_decision is None:
            continue
        peer_matches = [
            candidate for candidate in candidate_analyses
            if (
                _sector(candidate)
                and _sector(candidate) == held_sector
                and _is_buy_candidate(candidate, decision_map)
            )
        ]
        if not peer_matches:
            continue
        best_candidate = max(
            peer_matches,
            key=lambda candidate: _swap_score(held, candidate, weights, decision_map),
        )
        candidate_decision = _decision_for(best_candidate, decision_map)
        if candidate_decision is None:
            continue
        score = _swap_score(held, best_candidate, weights, decision_map)
        if score <= 0:
            continue
        held_ticker = str(getattr(held, "ticker", ""))
        candidate_ticker = str(getattr(best_candidate, "ticker", ""))
        weight = weights.get(held_ticker, 0.0)
        candidates.append({
            "held_ticker": held_ticker,
            "candidate_ticker": candidate_ticker,
            "swap_candidate_score": score,
            "summary": f"{held_ticker} 대비 {candidate_ticker} 교체 검토가 필요합니다.",
            "reasons": [
                f"{candidate_ticker} 확신도 {candidate_decision.conviction}가 {held_ticker}의 {held_decision.conviction}보다 높습니다.",
                f"동일 섹터 비교로 검토 맥락이 명확합니다: {_display_sector(held_sector)}.",
                (
                    f"{held_ticker} 비중이 포트폴리오 내 {weight:.0%}로 높아 교체 검토 우선순위가 있습니다."
                    if weight > 0
                    else f"{held_ticker}는 현재 보유 익스포저로 유지 타당성 점검이 필요합니다."
                ),
            ],
            "overlap_context": f"동일 섹터: {_display_sector(held_sector)}",
            "review_points": [
                f"{candidate_ticker}가 {held_ticker}보다 더 깔끔한 확신도 근거를 제공하는지 확인하세요.",
                f"{held_ticker} 비중 변경 전 포트폴리오 집중도 영향을 점검하세요.",
            ],
        })
    candidates.sort(
        key=lambda item: (-int(item["swap_candidate_score"]), item["held_ticker"], item["candidate_ticker"])
    )
    return candidates


def _build_event_exposure_items(
    held_analyses: Sequence[Any],
    portfolio_risk: dict[str, Any],
    decision_map: Mapping[str, TickerDecision],
) -> list[dict[str, Any]]:
    weights = _positions_by_weight(portfolio_risk)
    items: list[dict[str, Any]] = []
    for analysis in held_analyses:
        events = getattr(analysis, "upcoming_events", []) or []
        if not events:
            continue
        event = _nearest_event(events)
        decision = _decision_for(analysis, decision_map)
        conviction = decision.conviction if decision is not None else 0
        days_until = _days_until_value(event)
        weight = weights.get(str(getattr(analysis, "ticker", "")), 0.0)
        score = (
            max(0, EVENT_BASE_URGENCY - min(days_until, EVENT_MAX_DAYS_WINDOW))
            + max(0, round(weight * 100))
            + max(0, EVENT_CONVICTION_BASELINE - conviction)
        )
        ticker = str(getattr(analysis, "ticker", ""))
        label = _normalize_event_label(event)
        items.append({
            "ticker": ticker,
            "event_risk_score": score,
            "event_label": label,
            "event_date": str(event.get("date", "")),
            "days_until": days_until,
            "summary": f"{ticker}의 {label} 전 이벤트 노출 점검이 필요합니다.",
            "reasons": [
                f"{label} 일정이 {_days_phrase(days_until)} 앞으로 예정돼 있습니다.",
                (
                    f"{ticker} 확신도 {conviction} 구간이라 이벤트 전 점검 우선순위가 높습니다."
                    if conviction
                    else f"{ticker}는 보유 종목이어서 이벤트 전 노출 점검이 필요합니다."
                ),
                (
                    f"{ticker} 비중이 포트폴리오 내 {weight:.0%}입니다."
                    if weight > 0
                    else f"{ticker} 이벤트 전 포지션 규모와 변동성 노출을 확인하세요."
                ),
            ],
            "review_points": [
                f"{ticker} 이벤트 전 포지션 규모가 적절한지 확인하세요.",
                f"{label} 전후 변동성 확대 가능성을 점검하세요.",
            ],
        })
    items.sort(key=lambda item: (-int(item["event_risk_score"]), item["ticker"]))
    return items


def _build_today_priority_queue(
    swap_candidates: list[dict[str, Any]],
    event_exposure_items: list[dict[str, Any]],
    portfolio_risk: dict[str, Any],
) -> list[dict[str, Any]]:
    risk_bonus = _risk_grade_bonus(str(portfolio_risk.get("risk_grade", "")).strip())
    queue: list[dict[str, Any]] = []
    for item in swap_candidates:
        queue.append({
            "priority_type": "swap_review",
            "ticker": item["held_ticker"],
            "related_ticker": item["candidate_ticker"],
            "today_priority_score": int(item["swap_candidate_score"]) + risk_bonus,
            "summary": item["summary"],
            "reasons": list(item["reasons"]),
            "destination": "portfolio",
        })
    for item in event_exposure_items:
        queue.append({
            "priority_type": "event_review",
            "ticker": item["ticker"],
            "related_ticker": None,
            "today_priority_score": int(item["event_risk_score"]) + risk_bonus,
            "summary": item["summary"],
            "reasons": list(item["reasons"]),
            "destination": "portfolio",
        })
    queue.sort(
        key=lambda item: (
            -int(item["today_priority_score"]),
            str(item["ticker"]),
            str(item.get("related_ticker") or ""),
            str(item["priority_type"]),
        )
    )
    return queue


def _held_tickers(portfolio_summary: Any | None) -> set[str]:
    if portfolio_summary is None:
        return set()
    positions = getattr(portfolio_summary, "positions", None) or []
    return {
        str(getattr(position, "ticker", "")).strip()
        for position in positions
        if str(getattr(position, "ticker", "")).strip()
    }


def _positions_by_weight(portfolio_risk: dict[str, Any]) -> dict[str, float]:
    results: dict[str, float] = {}
    for item in portfolio_risk.get("positions_by_weight", []) or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip()
        if not ticker:
            continue
        try:
            results[ticker] = float(item.get("weight", 0.0) or 0.0)
        except (TypeError, ValueError):
            results[ticker] = 0.0
    return results


def _sector(analysis: Any) -> str:
    snapshot = getattr(analysis, "data_snapshot", {}) or {}
    if isinstance(snapshot, dict):
        return str(snapshot.get("Sector", "")).strip()
    return ""


def _decision_for(analysis: Any, decision_map: Mapping[str, TickerDecision]) -> TickerDecision | None:
    ticker = str(getattr(analysis, "ticker", "")).strip()
    if not ticker:
        return None
    return decision_map.get(ticker)


def _swap_score(
    held: Any,
    candidate: Any,
    weights: dict[str, float],
    decision_map: Mapping[str, TickerDecision],
) -> int:
    held_decision = _decision_for(held, decision_map)
    candidate_decision = _decision_for(candidate, decision_map)
    if held_decision is None or candidate_decision is None:
        return 0
    held_conviction = held_decision.conviction
    candidate_conviction = candidate_decision.conviction
    conviction_gap = max(0, candidate_conviction - held_conviction)
    weight_pressure = round(weights.get(str(getattr(held, "ticker", "")), 0.0) * 100)
    action_penalty = SWAP_ACTION_PENALTY if held_decision.action != "buy" else 0
    return conviction_gap + weight_pressure + action_penalty


def _is_buy_candidate(analysis: Any, decision_map: Mapping[str, TickerDecision]) -> bool:
    decision = _decision_for(analysis, decision_map)
    if decision is None:
        return False
    return decision.action == "buy"


def _risk_grade_bonus(risk_grade: str) -> int:
    bonuses = {
        "A": 0,
        "B": 3,
        "C": 6,
        "D": 10,
        "E": 14,
    }
    return bonuses.get(risk_grade.upper(), 0)


def _int_value(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return INVALID_DAYS_UNTIL


def _days_until_value(event: Mapping[str, Any]) -> int:
    return _int_value(event.get("days_until"))


def _normalize_event_label(event: Mapping[str, Any]) -> str:
    raw_label = str(event.get("label") or "").strip()
    raw_type = str(event.get("type") or "").strip()
    for candidate in (raw_label, raw_type):
        if not candidate:
            continue
        normalized = EVENT_LABEL_TRANSLATIONS.get(candidate.lower())
        if normalized:
            return normalized
    return "주요 일정"


def _display_sector(sector: str) -> str:
    cleaned = str(sector).strip()
    return cleaned if cleaned else "동일 업종"


def _days_phrase(days_until: int) -> str:
    if days_until <= 0:
        return "오늘"
    return f"{days_until}일"


def _nearest_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        events,
        key=lambda event: (
            _days_until_value(event),
            str(event.get("date", "")),
            str(event.get("label") or event.get("type") or ""),
        ),
    )


def _swap_empty_state(held_tickers: set[str], items: list[dict[str, Any]]) -> str:
    if items:
        return ""
    if not held_tickers:
        return "포트폴리오 보유 종목이 없어 교체 검토 후보를 만들지 않았습니다."
    return "오늘은 동일 섹터 내에서 더 나은 교체 후보가 없습니다."


def _event_empty_state(held_tickers: set[str], items: list[dict[str, Any]]) -> str:
    if items:
        return ""
    if not held_tickers:
        return "포트폴리오 보유 종목이 없어 이벤트 노출 점검 항목이 없습니다."
    return "오늘은 별도로 점검할 단기 이벤트 노출이 없습니다."


def _queue_empty_state(held_tickers: set[str], items: list[dict[str, Any]]) -> str:
    if items:
        return ""
    if not held_tickers:
        return "포트폴리오 보유 종목이 없어 PM 검토 큐를 만들지 않았습니다."
    return "오늘 바로 확인할 PM 우선 검토 항목이 없습니다."
