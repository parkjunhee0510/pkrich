from __future__ import annotations

from typing import Any

from src.types import CollectedTickerData, PortfolioSummary, WatchlistItem

_GROWTH_SECTORS = {"technology", "semiconductors"}
_DEFENSIVE_SECTORS = {"consumer staples", "utilities", "healthcare"}
_RATE_SENSITIVE_SECTORS = {"financials", "real estate", "utilities", "communication services"}
_CYCLICAL_SECTORS = {"industrials", "energy", "materials", "consumer discretionary"}
_CONSUMER_SECTORS = {"consumer staples", "consumer discretionary", "communication services"}


def attach_portfolio_macro_sensitivity(
    macro_context: dict[str, Any],
    portfolio_summary: PortfolioSummary | None,
    collected: dict[str, CollectedTickerData],
    watchlist: list[WatchlistItem] | None = None,
) -> dict[str, Any]:
    context = dict(macro_context or {})
    events = [event for event in context.get("upcoming_macro_events", []) if isinstance(event, dict)]
    if not events or portfolio_summary is None:
        context["portfolio_event_sensitivity"] = []
        context["ticker_macro_sensitivity"] = {}
        context["portfolio_sensitivity_summary"] = "N/A"
        return context

    watchlist_by_ticker = {item.ticker: item for item in watchlist or []}
    portfolio_tickers = [position.ticker for position in portfolio_summary.positions]

    event_rows: list[dict[str, Any]] = []
    ticker_rows: dict[str, list[dict[str, str]]] = {ticker: [] for ticker in portfolio_tickers}
    for event in events:
        sensitive_holdings = []
        for ticker in portfolio_tickers:
            market = collected.get(ticker)
            if market is None:
                continue
            watch_item = watchlist_by_ticker.get(ticker)
            sensitivity = _score_ticker_sensitivity(event, market, watch_item)
            if sensitivity is None:
                continue
            sensitive_holdings.append(sensitivity)
            ticker_rows.setdefault(ticker, []).append(
                {
                    "event_code": str(event.get("event_code") or event.get("type") or ""),
                    "label": str(event.get("label", "")),
                    "date": str(event.get("date", "")),
                    "sensitivity": sensitivity["sensitivity"],
                    "reason": sensitivity["reason"],
                }
            )

        sensitive_holdings.sort(key=lambda item: (_sensitivity_rank(item["sensitivity"]), item["ticker"]), reverse=True)
        event_rows.append(
            {
                **event,
                "sensitive_holdings": sensitive_holdings[:5],
            }
        )

    context["portfolio_event_sensitivity"] = event_rows
    context["ticker_macro_sensitivity"] = ticker_rows
    context["portfolio_sensitivity_summary"] = _build_portfolio_sensitivity_summary(event_rows)
    return context


def _score_ticker_sensitivity(
    event: dict[str, Any],
    market: CollectedTickerData,
    watch_item: WatchlistItem | None,
) -> dict[str, str] | None:
    event_code = str(event.get("event_code") or event.get("type") or "").upper()
    sector = _normalize_text(market.sector or (watch_item.sector if watch_item else ""))
    industry = _normalize_text(market.fundamental_metrics.get("industry", ""))
    keywords = [_normalize_text(keyword) for keyword in (watch_item.keywords if watch_item else [])]
    pe_value = _parse_numeric(market.pe_ratio)
    dividend_yield = _parse_numeric(market.dividend_yield)

    is_growth = sector in _GROWTH_SECTORS or any(token in industry for token in ["semiconductor", "software", "quantum", "cloud"])
    is_high_pe_growth = is_growth and pe_value is not None and pe_value >= 28
    is_low_dividend_growth = is_growth and (dividend_yield is None or dividend_yield <= 1.0)
    is_consumer = sector in _CONSUMER_SECTORS or any(token in " ".join(keywords) for token in ["iphone", "beverage", "wireless", "consumer"])
    is_cyclical = sector in _CYCLICAL_SECTORS or any(token in industry for token in ["industrial", "oil", "energy", "equipment"])
    is_defensive = sector in _DEFENSIVE_SECTORS
    is_rate_sensitive = sector in _RATE_SENSITIVE_SECTORS or (sector == "communication services" and dividend_yield is not None and dividend_yield >= 3.0)
    is_energy = sector == "energy"

    sensitivity = ""
    reason = ""
    if event_code in {"CPI", "PPI"}:
        if is_high_pe_growth or is_low_dividend_growth:
            sensitivity = "high"
            reason = "고PER 성장주 성격이 강해 인플레와 금리 재평가에 민감함"
        elif is_energy or is_cyclical or is_consumer:
            sensitivity = "medium"
            reason = "물가 경로 변화가 수요와 마진 전망에 함께 영향을 줄 수 있음"
    elif event_code == "FOMC":
        if is_rate_sensitive or is_high_pe_growth:
            sensitivity = "high"
            reason = "금리 경로 변화가 밸류에이션과 현금흐름 할인율에 직접 연결됨"
        elif is_defensive or is_cyclical:
            sensitivity = "medium"
            reason = "금리 스탠스 변화가 방어주와 경기민감주 상대 강도에 영향을 줄 수 있음"
    elif event_code in {"NFP", "UNRATE"}:
        if is_cyclical or is_energy:
            sensitivity = "high"
            reason = "고용과 경기 모멘텀이 업황 기대에 직접 반영되는 업종임"
        elif is_consumer or is_growth:
            sensitivity = "medium"
            reason = "노동시장 강도 변화가 소비와 멀티플 기대에 간접 영향을 줄 수 있음"
    elif event_code == "RETAIL_SALES":
        if is_consumer:
            sensitivity = "high"
            reason = "소비 지출 지표와 매출 기대가 직접 연결되는 업종임"
        elif is_cyclical or is_growth:
            sensitivity = "medium"
            reason = "수요 둔화 또는 강세 해석이 2차적으로 업황 기대에 반영될 수 있음"

    if not sensitivity:
        return None

    return {
        "ticker": market.ticker,
        "name": market.name,
        "sector": market.sector,
        "sensitivity": sensitivity,
        "reason": reason,
    }


def _build_portfolio_sensitivity_summary(event_rows: list[dict[str, Any]]) -> str:
    snippets: list[str] = []
    for event in event_rows[:3]:
        high_holdings = [item["ticker"] for item in event.get("sensitive_holdings", []) if item.get("sensitivity") == "high"]
        medium_holdings = [item["ticker"] for item in event.get("sensitive_holdings", []) if item.get("sensitivity") == "medium"]
        parts: list[str] = []
        if high_holdings:
            parts.append(f"high {', '.join(high_holdings[:3])}")
        if medium_holdings:
            parts.append(f"medium {', '.join(medium_holdings[:3])}")
        if parts:
            snippets.append(f"{event.get('event_code', event.get('type', 'EVENT'))}: {'; '.join(parts)}")
    return " | ".join(snippets) if snippets else "N/A"


def _normalize_text(value: str) -> str:
    return str(value or '').strip().lower()


def _parse_numeric(value: str) -> float | None:
    text = str(value or '').replace('%', '').replace('x', '').replace(',', '').strip()
    if text in {'', 'N/A'}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _sensitivity_rank(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(value, 0)
