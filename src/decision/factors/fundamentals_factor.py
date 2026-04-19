from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_float, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class FundamentalsFactor(DecisionFactor):
    name = "fundamentals"
    description = "Forward EPS 성장과 기관 보유 기반 기초체력"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del analysis, regime, signal_stats
        score = 0.0
        if collected is None:
            return FactorScore(value=0, confidence=0.2, reasoning="기초체력 데이터가 제한적이라 중립 반영")

        forward_eps = parse_float(collected.forward_eps)
        ttm_eps = parse_float(collected.eps)
        inst = parse_float(collected.held_by_institutions)
        parts: list[str] = []

        if forward_eps is not None and ttm_eps is not None and ttm_eps > 0:
            growth = (forward_eps - ttm_eps) / ttm_eps * 100
            if growth >= 20:
                score += 3
            elif growth >= 10:
                score += 1
            elif growth <= -10:
                score -= 3
            parts.append(f"선행 EPS 성장 {growth:+.1f}%")

        if inst is not None:
            if inst >= 60:
                score += 1
            elif inst < 30:
                score -= 1
            parts.append(f"기관 보유 {inst:.1f}%")

        return FactorScore(
            value=int(round(max(-6, min(6, score)))),
            confidence=score_confidence(forward_eps, ttm_eps, inst),
            reasoning=" / ".join(parts) if parts else "기초체력 보조 지표 부족",
        )
