"""Per-ticker decision layer with 8-factor conviction scoring.

Produces an action (buy/watch/avoid) and conviction score (0-100) for each
ticker based on quantitative factors. No LLM calls — purely rule-based for
reproducibility and speed.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path("config/decision_weights.yaml")

_REASON_TEMPLATES: dict[str, str] = {
    "valuation": "밸류에이션 양호 ({detail})",
    "momentum": "모멘텀 {detail}",
    "catalyst_recency": "촉매 {detail}",
    "signal_track_record": "시그널 승률 {detail}",
    "news_tone": "뉴스 톤 {detail}",
    "regime_adjustment": "시장 환경 {detail}",
    "earnings_pattern": "실적 패턴 {detail}",
    "fundamentals": "펀더멘털 {detail}",
}


def generate_decisions(
    analyses: list[TickerAnalysis],
    collected: dict[str, CollectedTickerData],
    regime: MarketRegime,
    signal_stats: dict[str, Any],
    run_date: date,
) -> list[TickerDecision]:
    """Generate investment decisions for all analyzed tickers.

    Never raises — returns empty list on failure.
    """
    try:
        config = _load_weights()
        return [
            _decide_ticker(analysis, collected.get(analysis.ticker), regime, signal_stats, run_date, config)
            for analysis in analyses
        ]
    except Exception:
        logger.exception("Decision layer failed")
        return []


def _decide_ticker(
    analysis: TickerAnalysis,
    data: CollectedTickerData | None,
    regime: MarketRegime,
    signal_stats: dict[str, Any],
    run_date: date,
    config: dict[str, Any],
) -> TickerDecision:
    """Compute conviction and action for a single ticker."""
    factors: dict[str, float] = {}

    factors["valuation"] = _score_valuation(analysis)
    factors["momentum"] = _score_momentum(analysis, data)
    factors["catalyst_recency"] = _score_catalyst_recency(analysis, run_date)
    factors["signal_track_record"] = _score_signal_track_record(analysis.ticker, signal_stats)
    factors["news_tone"] = _score_news_tone(analysis)
    factors["regime_adjustment"] = _score_regime_adjustment(regime, analysis)
    factors["earnings_pattern"] = _score_earnings_pattern(analysis)
    factors["fundamentals"] = _score_fundamentals(analysis, data)

    # Clamp each factor to its configured bounds
    factor_config = config.get("factors", {})
    for key, value in factors.items():
        bounds = factor_config.get(key, {})
        low = bounds.get("min", -100)
        high = bounds.get("max", 100)
        factors[key] = max(low, min(high, value))

    raw_total = sum(factors.values())
    # Normalize to 0-100 from theoretical range [-50, +120]
    conviction = max(0, min(100, int((raw_total + 50) / 170 * 100)))

    thresholds = config.get("thresholds", {})
    buy_threshold = thresholds.get("buy_risk_off", 75) if regime.regime == "risk_off" else thresholds.get("buy", 65)
    avoid_threshold = thresholds.get("avoid", 35)

    if conviction >= buy_threshold:
        action = "buy"
    elif conviction < avoid_threshold:
        action = "avoid"
    else:
        action = "watch"

    reason = _build_reason(factors)
    valid_until = _compute_valid_until(analysis, run_date, config)

    return TickerDecision(
        ticker=analysis.ticker,
        action=action,  # type: ignore[arg-type]
        conviction=conviction,
        reason=reason,
        valid_until=valid_until,
        factors=factors,
    )


def _score_valuation(analysis: TickerAnalysis) -> float:
    """Valuation factor (0-20): from valuation_score field."""
    vs = analysis.valuation_score
    if not vs:
        return 10  # neutral default
    score_str = vs.get("score", "")
    score_val = _parse_float(score_str)
    if score_val is None:
        return 10
    # score is typically 0-10, scale to 0-20
    return min(20, max(0, score_val * 2))


def _score_momentum(analysis: TickerAnalysis, data: CollectedTickerData | None) -> float:
    """Momentum factor (0-20): RS vs SPY, SMA position, RVOL."""
    score = 10.0  # neutral base

    pa = analysis.price_action
    rs = _parse_float(pa.get("rs_vs_spy"))
    if rs is not None:
        if rs >= 5:
            score += 5
        elif rs >= 2:
            score += 3
        elif rs <= -5:
            score -= 5
        elif rs <= -2:
            score -= 3

    vs_sma50 = _parse_float(pa.get("price_vs_sma50"))
    vs_sma200 = _parse_float(pa.get("price_vs_sma200"))
    if vs_sma50 is not None and vs_sma50 > 0 and vs_sma200 is not None and vs_sma200 > 0:
        score += 3
    elif vs_sma50 is not None and vs_sma50 < 0 and vs_sma200 is not None and vs_sma200 < 0:
        score -= 3

    rvol = _parse_float(pa.get("relative_volume"))
    if rvol is not None and rvol >= 1.3:
        score += 2

    return max(0, min(20, score))


def _score_catalyst_recency(analysis: TickerAnalysis, run_date: date) -> float:
    """Catalyst recency (-10 to +20): upcoming events and SEC filing freshness."""
    score = 0.0

    for event in analysis.upcoming_events:
        if event.get("type") == "earnings":
            days_until = _parse_int(event.get("days_until"))
            if days_until is not None:
                if days_until <= 3:
                    score += 20
                elif days_until <= 7:
                    score += 15
                elif days_until <= 14:
                    score += 10
                elif days_until <= 30:
                    score += 5
                break

    # Check news freshness — recent hard catalyst (SEC filings)
    for ref in analysis.news_references:
        if ref.catalyst_type == "hard" and ref.published_at:
            try:
                pub_date = date.fromisoformat(ref.published_at[:10])
                days_old = (run_date - pub_date).days
                if days_old <= 3:
                    score += 8
                elif days_old <= 7:
                    score += 4
                break
            except ValueError:
                continue

    if score == 0:
        score = -5  # no catalyst penalty

    return max(-10, min(20, score))


def _score_signal_track_record(ticker: str, signal_stats: dict[str, Any]) -> float:
    """Signal track record (-10 to +15): from signal_stats win rate."""
    recent = signal_stats.get("recent_signals", [])
    ticker_signals = [s for s in recent if s.get("ticker") == ticker]

    if not ticker_signals:
        return 0

    evaluated = [s for s in ticker_signals if s.get("return_5d") not in ("", "N/A", None)]
    if not evaluated:
        return 0

    wins = sum(1 for s in evaluated if _parse_float(s.get("return_5d", "0")) is not None and (_parse_float(s.get("return_5d", "0")) or 0) > 0)
    win_rate = wins / len(evaluated) if evaluated else 0

    if win_rate >= 0.7:
        return 15
    if win_rate >= 0.6:
        return 10
    if win_rate >= 0.5:
        return 5
    if win_rate < 0.3:
        return -10
    return 0


def _score_news_tone(analysis: TickerAnalysis) -> float:
    """News tone (-5 to +10): alignment with price momentum."""
    tone = analysis.news_tone
    if not tone:
        return 0

    tone_label = str(tone.get("label", "neutral")).lower()
    momentum_dir = _parse_float(analysis.price_action.get("rs_vs_spy"))

    if tone_label == "bullish":
        if momentum_dir is not None and momentum_dir > 0:
            return 10  # aligned bullish
        return 5  # bullish tone, no momentum confirmation
    if tone_label == "bearish":
        if momentum_dir is not None and momentum_dir < 0:
            return -5  # aligned bearish
        return -3
    return 0


def _score_regime_adjustment(regime: MarketRegime, analysis: TickerAnalysis) -> float:
    """Regime adjustment (-15 to +15): regime affects offensive vs defensive tickers."""
    sector = ""
    for ref in analysis.news_references[:1]:
        pass
    # Use data_snapshot sector or name heuristic
    snapshot = analysis.data_snapshot
    sector_raw = snapshot.get("Sector", "").lower()

    defensive_sectors = {"consumer defensive", "utilities", "healthcare", "consumer staples"}
    offensive_sectors = {"technology", "consumer cyclical", "communication services", "financial"}

    is_defensive = sector_raw in defensive_sectors
    is_offensive = sector_raw in offensive_sectors

    if regime.regime == "risk_on":
        if is_offensive:
            return 15
        if is_defensive:
            return 5
        return 10
    if regime.regime == "risk_off":
        if is_defensive:
            return 10
        if is_offensive:
            return -15
        return -5
    # neutral
    return 0


def _score_earnings_pattern(analysis: TickerAnalysis) -> float:
    """Earnings pattern (-10 to +10): consecutive beats/misses."""
    quarters = analysis.quarterly_financials
    if not quarters:
        return 0

    consecutive_beats = 0
    consecutive_misses = 0
    for q in quarters[:4]:
        bm = q.get("beat_miss", "").lower()
        if bm == "beat":
            consecutive_beats += 1
        elif bm == "miss":
            consecutive_misses += 1
        else:
            break

    if consecutive_beats >= 3:
        return 10
    if consecutive_beats >= 2:
        return 6
    if consecutive_misses >= 3:
        return -10
    if consecutive_misses >= 2:
        return -6
    return 0


def _score_fundamentals(analysis: TickerAnalysis, data: CollectedTickerData | None) -> float:
    """Fundamentals quality (0-10): Forward EPS growth, institutional ownership."""
    score = 5.0  # neutral base

    if data:
        forward_eps = _parse_float(data.forward_eps)
        ttm_eps = _parse_float(data.eps)
        if forward_eps is not None and ttm_eps is not None and ttm_eps > 0:
            growth = (forward_eps - ttm_eps) / ttm_eps * 100
            if growth >= 20:
                score += 3
            elif growth >= 10:
                score += 1
            elif growth <= -10:
                score -= 3

        inst = _parse_float(data.held_by_institutions)
        if inst is not None and inst >= 60:
            score += 2

    return max(0, min(10, score))


def _build_reason(factors: dict[str, float]) -> str:
    """Build a Korean reason string from top contributing factors."""
    sorted_factors = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)
    parts: list[str] = []
    for key, value in sorted_factors[:3]:
        if abs(value) < 1:
            continue
        direction = "양호" if value > 0 else "부진"
        template = _REASON_TEMPLATES.get(key, "{detail}")
        parts.append(template.format(detail=f"{direction} ({value:+.0f}점)"))

    return " / ".join(parts) if parts else "판단 근거 부족"


def _compute_valid_until(analysis: TickerAnalysis, run_date: date, config: dict[str, Any]) -> str:
    """Determine decision validity date."""
    vu_config = config.get("valid_until", {})
    earnings_window = vu_config.get("earnings_window_days", 30)
    default_days = vu_config.get("default_days", 7)

    for event in analysis.upcoming_events:
        if event.get("type") == "earnings":
            days_until = _parse_int(event.get("days_until"))
            if days_until is not None and days_until <= earnings_window:
                try:
                    return event["date"]
                except KeyError:
                    pass

    return (run_date + timedelta(days=default_days)).isoformat()


def _load_weights() -> dict[str, Any]:
    """Load decision weight configuration from YAML."""
    if _WEIGHTS_PATH.exists():
        try:
            with _WEIGHTS_PATH.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            logger.warning("Failed to load decision weights, using defaults")
    return {
        "factors": {},
        "thresholds": {"buy": 65, "buy_risk_off": 75, "avoid": 35},
        "valid_until": {"earnings_window_days": 30, "default_days": 7},
    }


def _parse_float(value: Any) -> float | None:
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


def _parse_int(value: Any) -> int | None:
    f = _parse_float(value)
    return int(f) if f is not None else None
