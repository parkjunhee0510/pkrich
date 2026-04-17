from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_float, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis
from src.utils.earnings_pattern import build_earnings_pattern


class EarningsFactor(DecisionFactor):
    name = "earnings_pattern"
    description = "실적 서프라이즈 패턴과 연속 beat/miss"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime, signal_stats
        if not analysis.quarterly_financials:
            return FactorScore(value=0, confidence=0.2, reasoning="실적 이력이 부족")

        pattern = build_earnings_pattern(analysis.quarterly_financials)
        score = 0.0
        beat_streak = int(pattern["beat_streak"])
        if beat_streak >= 3:
            score += 8
        elif beat_streak == 2:
            score += 5

        trend = str(pattern["surprise_trend"])
        if trend == "improving":
            score += 3
        elif trend == "deteriorating":
            score -= 3

        avg_surprise = parse_float(pattern["avg_surprise_pct"])
        if avg_surprise is not None:
            if avg_surprise >= 5:
                score += 2
            elif avg_surprise <= -5:
                score -= 2

        consecutive_misses = 0
        for quarter in analysis.quarterly_financials[:4]:
            beat_miss = str(quarter.get("beat_miss", "")).strip().lower()
            if beat_miss == "miss":
                consecutive_misses += 1
            else:
                break
        if consecutive_misses >= 3:
            score -= 8
        elif consecutive_misses >= 2:
            score -= 6

        parts: list[str] = []
        if beat_streak > 0:
            parts.append(f"연속 상회 {beat_streak}분기")
        trend_map = {
            "improving": "서프라이즈 추세 개선",
            "deteriorating": "서프라이즈 추세 악화",
            "stable": "서프라이즈 추세 안정",
            "insufficient_data": "서프라이즈 데이터 부족",
        }
        parts.append(trend_map.get(trend, trend))
        if avg_surprise is not None:
            parts.append(f"평균 서프라이즈 {avg_surprise:+.1f}%")
        if consecutive_misses >= 2:
            parts.append(f"연속 미스 {consecutive_misses}분기")

        return FactorScore(
            value=int(round(max(-10, min(10, score)))),
            confidence=score_confidence(analysis.quarterly_financials, pattern),
            reasoning=" / ".join(parts),
        )
