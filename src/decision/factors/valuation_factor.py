from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_float, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class ValuationFactor(DecisionFactor):
    name = "valuation"
    description = "밸류에이션 점수와 현재 가격 매력도"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime, signal_stats
        vs = analysis.valuation_score
        if not vs:
            return FactorScore(value=0, confidence=0.3, reasoning="밸류에이션 데이터가 제한적이라 중립 반영")

        score_val = parse_float(vs.get("score", ""))
        if score_val is None:
            return FactorScore(value=0, confidence=0.3, reasoning="밸류에이션 점수를 읽지 못해 중립 반영")

        scaled = max(-12, min(12, (score_val - 5.0) * 4.0))
        confidence = score_confidence(score_val, vs.get("assessment"), vs.get("factors"))
        reasoning = str(vs.get("assessment") or f"밸류에이션 점수 {score_val:.1f}/10 반영")
        return FactorScore(value=int(round(scaled)), confidence=confidence, reasoning=reasoning)
