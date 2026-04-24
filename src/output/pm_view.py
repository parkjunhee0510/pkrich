from __future__ import annotations

from typing import Any

SWAP_ACTION_PENALTY = 10
EVENT_BASE_URGENCY = 60
EVENT_MAX_DAYS_WINDOW = 30
EVENT_CONVICTION_BASELINE = 70


def build_pm_view(
    analyses: list[Any],
    *,
    as_of: str,
    portfolio_summary: Any | None,
    portfolio_risk: dict[str, Any] | None,
    decision_map: dict[str, Any],
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
    held_analyses: list[Any],
    candidate_analyses: list[Any],
    portfolio_risk: dict[str, Any],
    decision_map: dict[str, Any],
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
            "summary": (
                f"Review {held_ticker} against {candidate_ticker} within {held_sector or 'the same'} exposure."
            ),
            "reasons": [
                (
                    f"{candidate_ticker} conviction is {int(getattr(candidate_decision, 'conviction', 0))}, "
                    f"above {held_ticker} at {int(getattr(held_decision, 'conviction', 0))}."
                ),
                f"Same sector match keeps the comparison explainable: {held_sector or 'N/A'}.",
                (
                    f"{held_ticker} carries portfolio pressure at {weight:.0%} weight."
                    if weight > 0
                    else f"{held_ticker} remains the held exposure under review."
                ),
            ],
            "overlap_context": f"Same sector: {held_sector or 'N/A'}",
            "review_points": [
                f"Check whether {candidate_ticker} offers cleaner conviction support than {held_ticker}.",
                f"Review concentration impact before changing {held_ticker} exposure.",
            ],
        })
    candidates.sort(
        key=lambda item: (-int(item["swap_candidate_score"]), item["held_ticker"], item["candidate_ticker"])
    )
    return candidates


def _build_event_exposure_items(
    held_analyses: list[Any],
    portfolio_risk: dict[str, Any],
    decision_map: dict[str, Any],
) -> list[dict[str, Any]]:
    weights = _positions_by_weight(portfolio_risk)
    items: list[dict[str, Any]] = []
    for analysis in held_analyses:
        events = getattr(analysis, "upcoming_events", []) or []
        if not events:
            continue
        event = _nearest_event(events)
        decision = _decision_for(analysis, decision_map)
        conviction = int(getattr(decision, "conviction", 0)) if decision is not None else 0
        days_until = _int_value(event.get("days_until"))
        weight = weights.get(str(getattr(analysis, "ticker", "")), 0.0)
        score = (
            max(0, EVENT_BASE_URGENCY - min(days_until, EVENT_MAX_DAYS_WINDOW))
            + max(0, round(weight * 100))
            + max(0, EVENT_CONVICTION_BASELINE - conviction)
        )
        ticker = str(getattr(analysis, "ticker", ""))
        label = str(event.get("label") or event.get("type") or "Upcoming event")
        items.append({
            "ticker": ticker,
            "event_risk_score": score,
            "event_label": label,
            "event_date": str(event.get("date", "")),
            "days_until": days_until,
            "summary": f"Review {ticker} event exposure before {label.lower()}.",
            "reasons": [
                f"{label} is scheduled in D-{days_until}.",
                (
                    f"{ticker} conviction is only {conviction}, which raises review urgency into the event window."
                    if conviction
                    else f"{ticker} is a held name with a near-term event window."
                ),
                (
                    f"{ticker} carries {weight:.0%} portfolio weight."
                    if weight > 0
                    else f"Confirm event sizing for {ticker} against current portfolio risk."
                ),
            ],
            "review_points": [
                f"Check whether {ticker} event exposure is appropriately sized.",
                f"Confirm timing and volatility context for {label.lower()}.",
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


def _decision_for(analysis: Any, decision_map: dict[str, Any]) -> Any | None:
    ticker = str(getattr(analysis, "ticker", "")).strip()
    if not ticker:
        return None
    return decision_map.get(ticker)


def _swap_score(held: Any, candidate: Any, weights: dict[str, float], decision_map: dict[str, Any]) -> int:
    held_decision = _decision_for(held, decision_map)
    candidate_decision = _decision_for(candidate, decision_map)
    if held_decision is None or candidate_decision is None:
        return 0
    held_conviction = int(getattr(held_decision, "conviction", 0))
    candidate_conviction = int(getattr(candidate_decision, "conviction", 0))
    conviction_gap = max(0, candidate_conviction - held_conviction)
    weight_pressure = round(weights.get(str(getattr(held, "ticker", "")), 0.0) * 100)
    action_penalty = SWAP_ACTION_PENALTY if str(getattr(held_decision, "action", "")).strip() != "buy" else 0
    return conviction_gap + weight_pressure + action_penalty


def _is_buy_candidate(analysis: Any, decision_map: dict[str, Any]) -> bool:
    decision = _decision_for(analysis, decision_map)
    if decision is None:
        return False
    return str(getattr(decision, "action", "")).strip().lower() == "buy"


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
        return 0


def _nearest_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    return min(
        events,
        key=lambda event: (
            _int_value(event.get("days_until")),
            str(event.get("date", "")),
            str(event.get("label") or event.get("type") or ""),
        ),
    )


def _swap_empty_state(held_tickers: set[str], items: list[dict[str, Any]]) -> str:
    if items:
        return ""
    if not held_tickers:
        return "No swap review candidates because no portfolio holdings are available today."
    return "No swap review candidates today. Current holdings do not have a stronger same-sector alternative."


def _event_empty_state(held_tickers: set[str], items: list[dict[str, Any]]) -> str:
    if items:
        return ""
    if not held_tickers:
        return "No event exposure review items because no portfolio holdings are available today."
    return "No urgent event exposure reviews today. Held names do not show near-term event pressure."


def _queue_empty_state(held_tickers: set[str], items: list[dict[str, Any]]) -> str:
    if items:
        return ""
    if not held_tickers:
        return "No PM priority queue is available because no portfolio holdings are loaded."
    return "No PM priority queue items today. Current portfolio review pressure is limited."
