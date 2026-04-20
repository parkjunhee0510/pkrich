from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_float, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class NewsToneFactor(DecisionFactor):
    name = "news_tone"
    description = "뉴스 톤과 가격 흐름의 정합성"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime, signal_stats
        tone = analysis.news_tone
        if not tone:
            return FactorScore(value=0, confidence=0.2, reasoning="뉴스 톤 데이터가 부족")

        tone_label = str(tone.get("label", "neutral")).lower()
        momentum_dir = parse_float(analysis.price_action.get("rs_vs_spy"))

        if tone_label == "bullish":
            if momentum_dir is not None and momentum_dir > 0:
                return FactorScore(value=10, confidence=0.9, reasoning="강세 뉴스와 가격 흐름이 같은 방향")
            return FactorScore(value=5, confidence=0.6, reasoning="강세 뉴스지만 가격 확인은 제한적")
        if tone_label == "bearish":
            if momentum_dir is not None and momentum_dir < 0:
                return FactorScore(value=-5, confidence=0.9, reasoning="약세 뉴스와 가격 흐름이 같은 방향")
            return FactorScore(value=-3, confidence=0.6, reasoning="약세 뉴스가 확인돼 보수적으로 반영")
        return FactorScore(value=0, confidence=score_confidence(tone, momentum_dir), reasoning="뉴스 톤이 중립")
