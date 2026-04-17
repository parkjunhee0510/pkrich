from __future__ import annotations

from datetime import date
from typing import Any

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.weekly_insight_module import WeeklyInsightModule
from src.utils.model_config import load_model_profile


def generate_weekly_insight(
    *,
    iso_year: int,
    iso_week: int,
    start_date: str,
    end_date: str,
    market_moves: list[Any],
    sector_performance: list[Any],
    top_gainers: list[Any],
    top_losers: list[Any],
    repeated_news: list[Any],
    signal_summary: list[str],
    action_items: list[str],
) -> str:
    report = generate_weekly_report(
        iso_year=iso_year,
        iso_week=iso_week,
        start_date=start_date,
        end_date=end_date,
        market_moves=market_moves,
        sector_performance=sector_performance,
        top_gainers=top_gainers,
        top_losers=top_losers,
        repeated_news=repeated_news,
        signal_summary=signal_summary,
        action_items=action_items,
    )
    return str(report.get("summary", "")).strip()



def generate_weekly_report(
    *,
    iso_year: int,
    iso_week: int,
    start_date: str,
    end_date: str,
    market_moves: list[Any],
    sector_performance: list[Any],
    top_gainers: list[Any],
    top_losers: list[Any],
    repeated_news: list[Any],
    signal_summary: list[str],
    action_items: list[str],
    macro_context: dict[str, Any] | None = None,
    market_regime: dict[str, Any] | Any | None = None,
    portfolio_risk: dict[str, Any] | None = None,
    decisions: list[Any] | None = None,
    week_days: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    decision_items = sorted(
        [
            {
                "ticker": str(getattr(item, "ticker", "")),
                "action": str(getattr(item, "action", "")),
                "conviction": int(getattr(item, "conviction", 0) or 0),
                "reason": str(getattr(item, "reason", "")),
            }
            for item in (decisions or [])
            if getattr(item, "ticker", "")
        ],
        key=lambda item: item["conviction"],
        reverse=True,
    )
    latest_day = week_days[-1] if week_days else {}
    ticker_map = {
        str(item.get("ticker", "")).strip(): item
        for item in latest_day.get("tickers", [])
        if isinstance(item, dict)
    }
    top_conviction_items = []
    for item in decision_items[:5]:
        ticker_payload = ticker_map.get(item["ticker"], {})
        top_conviction_items.append(
            {
                **item,
                "catalyst": str(ticker_payload.get("signal_or_takeaway", "")).strip() or "촉매 요약 없음",
            }
        )

    mover_payload = []
    combined_movers = sorted(
        [*top_gainers[:3], *top_losers[:3]],
        key=lambda move: abs(getattr(move, "weekly_change_value", 0.0)),
        reverse=True,
    )[:3]
    for item in combined_movers:
        ticker_payload = ticker_map.get(getattr(item, "ticker", ""), {})
        key_news = ticker_payload.get("key_news", [])
        catalyst = key_news[0] if key_news and isinstance(key_news[0], str) else "반복 촉매 데이터 부족"
        decision_entry = next((entry for entry in decision_items if entry["ticker"] == getattr(item, "ticker", "")), None)
        mover_payload.append(
            {
                "ticker": getattr(item, "ticker", "N/A"),
                "name": getattr(item, "name", getattr(item, "ticker", "N/A")),
                "weekly_change": getattr(item, "weekly_change", "N/A"),
                "catalyst": catalyst,
                "decision_change": f"{decision_entry['action']} ({decision_entry['conviction']})" if decision_entry else "이번 주 decision 변화 데이터 없음",
            }
        )

    next_macro_events = []
    for event in (macro_context or {}).get("upcoming_macro_events", []):
        if not isinstance(event, dict):
            continue
        try:
            days_until = int(str(event.get("days_until", "999") or "999"))
        except ValueError:
            continue
        if days_until <= 7:
            next_macro_events.append(event)

    weekly_inputs = {
        "iso_year": iso_year,
        "iso_week": iso_week,
        "start_date": start_date,
        "end_date": end_date,
        "market_moves": [
            {
                "label": getattr(item, "label", "N/A"),
                "weekly_change": getattr(item, "weekly_change", "N/A"),
                "start_price": getattr(item, "start_price", "N/A"),
                "end_price": getattr(item, "end_price", "N/A"),
            }
            for item in market_moves[:5]
        ],
        "sector_performance": [
            {
                "sector": getattr(item, "sector", "N/A"),
                "average_weekly_change": getattr(item, "average_weekly_change", "N/A"),
                "ticker_count": getattr(item, "ticker_count", 0),
            }
            for item in sector_performance[:5]
        ],
        "top_movers": mover_payload,
        "repeated_news": [
            {
                "summary": getattr(item, "summary", "N/A"),
                "source": getattr(item, "source", "N/A"),
                "count": getattr(item, "count", 0),
                "tickers": getattr(item, "tickers", []),
            }
            for item in repeated_news[:5]
        ],
        "signal_summary": signal_summary[:5],
        "action_items": action_items[:5],
        "macro_context": macro_context or {},
        "market_regime": _serialize_market_regime(market_regime),
        "portfolio_risk": portfolio_risk or {},
        "next_macro_events": next_macro_events[:5],
        "top_conviction_items": top_conviction_items,
        "market_environment_details": _build_market_environment_details(market_moves, sector_performance, next_macro_events),
    }
    model_profile = load_model_profile()
    ctx = AnalysisContext(
        watchlist=[],
        collected={},
        news_map={},
        run_date=_safe_date(end_date),
        model_profile=model_profile,
        macro_context=macro_context or {},
        metadata={"weekly_inputs": weekly_inputs},
    )
    module = WeeklyInsightModule()
    result = module.analyze(ctx)
    portfolio_result = result.portfolio_result or {}
    weekly_report = portfolio_result.get("weekly_report")
    return weekly_report if isinstance(weekly_report, dict) else {}



def _build_market_environment_details(
    market_moves: list[Any],
    sector_performance: list[Any],
    next_macro_events: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    if market_moves:
        lines.append(", ".join(f"{item.label} {item.weekly_change}" for item in market_moves[:3]))
    if sector_performance:
        lines.append(", ".join(f"{item.sector} {item.average_weekly_change}" for item in sector_performance[:3]))
    if next_macro_events:
        lines.append(
            ", ".join(
                f"{event.get('date', 'N/A')} {event.get('label', '매크로 이벤트')} (D-{event.get('days_until', '?')})"
                for event in next_macro_events[:3]
            )
        )
    return lines



def _serialize_market_regime(market_regime: dict[str, Any] | Any | None) -> dict[str, Any]:
    if market_regime is None:
        return {}
    if isinstance(market_regime, dict):
        return dict(market_regime)
    return {
        "regime": getattr(market_regime, "regime", ""),
        "confidence": getattr(market_regime, "confidence", 0),
        "implication": getattr(market_regime, "implication", ""),
    }



def _safe_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()
