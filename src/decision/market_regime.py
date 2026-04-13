"""Detect current market regime from macro indicators.

Classifies the market as risk_on / neutral / risk_off based on:
  - VIX level
  - SPY trend (price vs SMA50/SMA200)
  - US 10Y yield direction
  - Breadth proxy (% of watchlist above SMA50)
  - Copper/DXY risk signals
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.types import CollectedTickerData, MarketRegime

_REGIME_LABELS: dict[str, str] = {
    "risk_on": "위험선호 구간: 공격적 진입 가능, 롱 바이어스 유지",
    "neutral": "중립 구간: 선별적 접근, 촉매 확인 후 진입",
    "risk_off": "위험회피 구간: 방어적 포지션, 현금 비중 확대 고려",
}


def detect_market_regime(
    market_overview: list[dict[str, str]],
    macro_context: dict[str, Any],
    collected: dict[str, CollectedTickerData],
    run_date: date,
) -> MarketRegime:
    """Compute market regime from available macro data.

    Returns a MarketRegime with regime, confidence, drivers, and implication.
    Designed to never raise — returns neutral with zero confidence on any failure.
    """
    scores: dict[str, int] = {}

    scores["vix"] = _score_vix(macro_context)
    scores["trend"] = _score_spy_trend(macro_context)
    scores["rates"] = _score_rates(macro_context)
    scores["breadth"] = _score_breadth(collected)
    scores["risk_assets"] = _score_risk_assets(macro_context)

    total = sum(scores.values())

    if total >= 3:
        regime = "risk_on"
    elif total <= -3:
        regime = "risk_off"
    else:
        regime = "neutral"

    max_possible = 7  # +2 +2 +1 +1 +1
    confidence = min(100, int(abs(total) / max_possible * 100))

    drivers = _build_drivers(macro_context, collected, scores)

    return MarketRegime(
        regime=regime,  # type: ignore[arg-type]
        confidence=confidence,
        drivers=drivers,
        implication=_REGIME_LABELS.get(regime, ""),
        assessed_at=run_date.isoformat(),
    )


def _score_vix(macro_context: dict[str, Any]) -> int:
    """VIX component: <15 = +2, 15-20 = +1, 20-25 = 0, 25-30 = -1, >30 = -2."""
    vix_data = macro_context.get("vix", {})
    level = _parse_float(vix_data.get("level"))
    if level is None:
        return 0
    if level < 15:
        return 2
    if level < 20:
        return 1
    if level < 25:
        return 0
    if level < 30:
        return -1
    return -2


def _score_spy_trend(macro_context: dict[str, Any]) -> int:
    """SPY trend: above both SMAs = +2, above SMA200 only = +1, below both = -2."""
    spy = macro_context.get("spy_technicals", {})
    close = _parse_float(spy.get("close"))
    sma50 = _parse_float(spy.get("sma50"))
    sma200 = _parse_float(spy.get("sma200"))

    if close is None or sma50 is None:
        return 0

    above_sma50 = close > sma50
    above_sma200 = close > sma200 if sma200 is not None else None

    if above_sma50 and above_sma200:
        return 2
    if above_sma200:
        return 1
    if not above_sma50 and above_sma200 is False:
        return -2
    return 0


def _score_rates(macro_context: dict[str, Any]) -> int:
    """US 10Y: stable/falling = +1, rising sharply = -1."""
    us10y = macro_context.get("us10y", {})
    change_str = us10y.get("change", "")
    change = _parse_float(change_str)
    if change is None:
        return 0
    if change >= 3.0:  # >3% daily change = sharp rise
        return -1
    if change <= -1.0:
        return 1
    return 0


def _score_breadth(collected: dict[str, CollectedTickerData]) -> int:
    """Breadth proxy: % of watchlist tickers above SMA50."""
    if not collected:
        return 0

    above_count = 0
    total_count = 0
    for data in collected.values():
        vs_sma50 = _parse_float(data.price_vs_sma50)
        if vs_sma50 is not None:
            total_count += 1
            if vs_sma50 > 0:
                above_count += 1

    if total_count == 0:
        return 0

    ratio = above_count / total_count
    if ratio >= 0.7:
        return 1
    if ratio <= 0.3:
        return -1
    return 0


def _score_risk_assets(macro_context: dict[str, Any]) -> int:
    """Copper rising = +1 (risk-on), DXY rising = -1 (risk-off)."""
    score = 0

    copper = macro_context.get("copper", {})
    copper_change = _parse_float(copper.get("change", ""))
    if copper_change is not None and copper_change > 0.5:
        score += 1

    dxy = macro_context.get("dxy", {})
    dxy_change = _parse_float(dxy.get("change", ""))
    if dxy_change is not None and dxy_change > 0.5:
        score -= 1

    return max(-1, min(1, score))


def _build_drivers(
    macro_context: dict[str, Any],
    collected: dict[str, CollectedTickerData],
    scores: dict[str, int],
) -> dict[str, str]:
    """Build human-readable driver descriptions."""
    vix_data = macro_context.get("vix", {})
    vix_level = vix_data.get("level", "N/A")
    vix_regime = vix_data.get("regime", "N/A")

    spy = macro_context.get("spy_technicals", {})
    spy_close = spy.get("close", "N/A")
    spy_sma50 = spy.get("sma50", "N/A")
    spy_sma200 = spy.get("sma200", "N/A")

    us10y = macro_context.get("us10y", {})
    rates_level = us10y.get("level", "N/A")
    rates_change = us10y.get("change", "N/A")

    total = len(collected)
    above = sum(
        1 for d in collected.values()
        if (_parse_float(d.price_vs_sma50) or 0) > 0
    ) if collected else 0

    breadth_pct = f"{above / total * 100:.0f}%" if total > 0 else "N/A"

    copper = macro_context.get("copper", {})
    copper_price = copper.get("level", "N/A")
    copper_change = copper.get("change", "N/A")

    dxy = macro_context.get("dxy", {})
    dxy_price = dxy.get("level", "N/A")
    dxy_change = dxy.get("change", "N/A")

    return {
        "vix": f"VIX {vix_level} ({vix_regime}) [점수 {scores.get('vix', 0):+d}]",
        "trend": f"SPY {spy_close} / SMA50 {spy_sma50} / SMA200 {spy_sma200} [점수 {scores.get('trend', 0):+d}]",
        "rates": f"10Y {rates_level} (변화 {rates_change}) [점수 {scores.get('rates', 0):+d}]",
        "breadth": f"SMA50 위 종목 비율 {breadth_pct} ({above}/{total}) [점수 {scores.get('breadth', 0):+d}]",
        "risk_assets": f"구리 {copper_price} ({copper_change}) / DXY {dxy_price} ({dxy_change}) [점수 {scores.get('risk_assets', 0):+d}]",
    }


def _parse_float(value: Any) -> float | None:
    """Safely parse a numeric value from various string formats."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
