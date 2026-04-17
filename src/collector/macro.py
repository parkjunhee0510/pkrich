"""Collect macro context: VIX, rates, and upcoming macro events."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from src.collector.finnhub import collect_finnhub_economic_calendar, is_finnhub_ready
from src.utils.network import can_open_tcp_connection

logger = logging.getLogger(__name__)

# Static fallback calendar kept as a safety net when live collection is unavailable.
_FALLBACK_EVENT_SCHEDULE: dict[str, tuple[list[str], dict[str, object]]] = {
    "FOMC": (
        [
            "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
            "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
        ],
        {
            "category": "rates",
            "label": "FOMC 금리 결정",
            "impact": "high",
            "market_bias": "매파적 결정은 장기 성장주에 압력을 줄 수 있습니다.",
            "description": "연준의 금리 경로와 점도표는 금리 민감 자산에 직접 영향을 줍니다.",
            "sensitivity_tags": ["long_duration_growth", "financials", "dividend"],
        },
    ),
    "CPI": (
        [
            "2026-01-14", "2026-02-11", "2026-03-11", "2026-04-14",
            "2026-05-13", "2026-06-10", "2026-07-14", "2026-08-12",
            "2026-09-15", "2026-10-13", "2026-11-12", "2026-12-09",
        ],
        {
            "category": "inflation",
            "label": "CPI 소비자물가지수",
            "impact": "high",
            "market_bias": "예상보다 높은 CPI는 금리 기대를 높여 성장주 밸류에이션에 부담을 줄 수 있습니다.",
            "description": "소비자물가는 금리 기대와 주식 밸류에이션에 직접 영향을 줍니다.",
            "sensitivity_tags": ["long_duration_growth", "consumer", "energy", "industrials"],
        },
    ),
    "PPI": (
        [
            "2026-01-15", "2026-02-12", "2026-03-12", "2026-04-15",
            "2026-05-14", "2026-06-11", "2026-07-15", "2026-08-13",
            "2026-09-16", "2026-10-14", "2026-11-13", "2026-12-10",
        ],
        {
            "category": "inflation",
            "label": "PPI 생산자물가지수",
            "impact": "high",
            "market_bias": "생산자물가 상승은 기업 마진을 압박하고 CPI 리스크를 예고할 수 있습니다.",
            "description": "생산자물가는 비용 압력과 마진 리스크를 조기에 파악하는 지표입니다.",
            "sensitivity_tags": ["industrials", "energy", "materials", "consumer"],
        },
    ),
    "NFP": (
        [
            "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
            "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
            "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
        ],
        {
            "category": "labor",
            "label": "NFP 비농업고용",
            "impact": "high",
            "market_bias": "강한 고용 지표는 성장 기대를 높이지만 금리 우려를 되살릴 수 있습니다.",
            "description": "고용 증가는 노동 강도, 성장, 금리 민감도를 파악하는 핵심 지표입니다.",
            "sensitivity_tags": ["industrials", "energy", "consumer", "long_duration_growth"],
        },
    ),
    "UNRATE": (
        [
            "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
            "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
            "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
        ],
        {
            "category": "labor",
            "label": "실업률",
            "impact": "high",
            "market_bias": "실업률 상승 또는 하락은 성장 기대를 빠르게 변화시킵니다.",
            "description": "실업률은 노동시장의 냉각 또는 과열 신호를 제공합니다.",
            "sensitivity_tags": ["industrials", "energy", "consumer", "financials"],
        },
    ),
    "RETAIL_SALES": (
        [
            "2026-01-15", "2026-02-13", "2026-03-17", "2026-04-15",
            "2026-05-15", "2026-06-16", "2026-07-16", "2026-08-14",
            "2026-09-17", "2026-10-15", "2026-11-17", "2026-12-15",
        ],
        {
            "category": "consumer",
            "label": "소매판매",
            "impact": "high",
            "market_bias": "강한 소비 지출은 경기민감주에 유리하지만 금리 재평가를 자극할 수 있습니다.",
            "description": "소매판매는 미국 소비자 수요의 강도를 측정하는 지표입니다.",
            "sensitivity_tags": ["consumer", "communication", "industrials"],
        },
    ),
}


def collect_macro_context(
    run_date: date,
    *,
    vix_data: dict[str, Any] | None = None,
    lookahead_days: int = 14,
) -> dict[str, Any]:
    """Return macro context dict for the given date."""
    context: dict[str, Any] = {}

    if vix_data:
        context["vix"] = {
            "level": vix_data.get("price", "N/A"),
            "change": vix_data.get("change_percent", "N/A"),
            "regime": _classify_vix_regime(vix_data.get("price")),
        }
    else:
        context["vix"] = {"level": "N/A", "change": "N/A", "regime": "N/A"}

    context["upcoming_macro_events"] = _find_upcoming_events(run_date, lookahead_days)
    context.update(_collect_macro_market_series())
    context["spy_technicals"] = _collect_spy_technicals()
    return context


def _classify_vix_regime(vix_level: Any) -> str:
    if vix_level is None or vix_level == "N/A":
        return "N/A"
    try:
        level = float(str(vix_level).replace(",", ""))
    except (ValueError, TypeError):
        return "N/A"

    if level < 15:
        return "낮은 변동성"
    if level < 20:
        return "정상 범위"
    if level < 30:
        return "경계"
    return "공포"


def _find_upcoming_events(run_date: date, lookahead_days: int) -> list[dict[str, str]]:
    if is_finnhub_ready():
        try:
            live_events = collect_finnhub_economic_calendar(run_date, lookahead_days=lookahead_days)
            if live_events:
                return live_events
        except Exception:
            logger.exception("Live macro calendar lookup failed; falling back to static schedule.")

    cutoff = run_date + timedelta(days=lookahead_days)
    events: list[dict[str, str]] = []
    for event_code, (date_list, meta) in _FALLBACK_EVENT_SCHEDULE.items():
        for date_str in date_list:
            event_date = _safe_parse_date(date_str)
            if event_date is None or not (run_date <= event_date <= cutoff):
                continue
            days_until = (event_date - run_date).days
            events.append(
                {
                    "type": event_code,
                    "event_code": event_code,
                    "category": str(meta["category"]),
                    "date": date_str,
                    "days_until": str(days_until),
                    "label": str(meta["label"]),
                    "impact": str(meta["impact"]),
                    "source": "fallback",
                    "actual": "N/A",
                    "consensus": "N/A",
                    "previous": "N/A",
                    "surprise_direction": "N/A",
                    "market_bias": str(meta["market_bias"]),
                    "description": str(meta["description"]),
                    "sensitivity_tags": ",".join(meta["sensitivity_tags"]),
                }
            )

    events.sort(key=lambda e: (e.get("date", ""), e.get("event_code", "")))
    return events


def _safe_parse_date(date_str: str) -> date | None:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


def _collect_macro_market_series() -> dict[str, dict[str, str]]:
    if not can_open_tcp_connection("query1.finance.yahoo.com", 443):
        return {}

    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return {}

    symbol_map: dict[str, tuple[str, str]] = {
        "us10y": ("^TNX", "US 10Y"),
        "dxy": ("DX-Y.NYB", "Dollar Index"),
        "copper": ("HG=F", "Copper"),
    }
    result: dict[str, dict[str, str]] = {}
    for key, (symbol, label) in symbol_map.items():
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", interval="1d")
            if history is None or history.empty:
                continue
            close_series = history["Close"].dropna()
            if close_series.empty:
                continue
            latest = float(close_series.iloc[-1])
            previous = float(close_series.iloc[-2]) if len(close_series) > 1 else latest
            change_pct = ((latest - previous) / previous * 100) if previous else 0.0
            result[key] = {
                "label": label,
                "level": f"{latest:,.2f}",
                "price": f"{latest:,.2f}",
                "change": f"{change_pct:+.2f}%",
            }
        except Exception:
            continue
    return result


def _collect_spy_technicals() -> dict[str, str]:
    """Fetch SPY close, SMA50, SMA200, RSI14 via yfinance."""
    if not can_open_tcp_connection("query1.finance.yahoo.com", 443):
        return {}

    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return {}

    try:
        ticker = yf.Ticker("SPY")
        history = ticker.history(period="210d", interval="1d")
        if history is None or history.empty:
            return {}
        close_series = history["Close"].dropna()
        if len(close_series) < 50:
            return {}

        latest_close = float(close_series.iloc[-1])
        sma50 = float(close_series.tail(50).mean())
        sma200 = float(close_series.tail(200).mean()) if len(close_series) >= 200 else None

        delta = close_series.diff()
        gain = delta.where(delta > 0, 0.0).tail(15)
        loss = (-delta.where(delta < 0, 0.0)).tail(15)
        avg_gain = float(gain.mean())
        avg_loss = float(loss.mean())
        rsi_14 = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0

        result: dict[str, str] = {
            "close": f"{latest_close:.2f}",
            "sma50": f"{sma50:.2f}",
            "rsi14": f"{rsi_14:.1f}",
        }
        if sma200 is not None:
            result["sma200"] = f"{sma200:.2f}"
        return result
    except Exception:
        logger.debug("SPY technicals collection failed", exc_info=True)
        return {}
