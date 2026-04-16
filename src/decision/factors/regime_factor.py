from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class RegimeFactor(DecisionFactor):
    name = "regime_adjustment"
    description = "시장 레짐에 따른 방어주/공격주 조정"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, signal_stats
        sector_raw = str(analysis.data_snapshot.get("Sector", "")).lower()
        defensive = {"consumer defensive", "utilities", "healthcare", "consumer staples"}
        offensive = {"technology", "consumer cyclical", "communication services", "financial"}
        is_defensive = sector_raw in defensive
        is_offensive = sector_raw in offensive

        if regime.regime == "risk_on":
            if is_offensive:
                value = 15
                reasoning = "리스크온 환경에서 공격주 선호"
            elif is_defensive:
                value = 5
                reasoning = "리스크온 환경에서도 방어주 프리미엄 유지"
            else:
                value = 10
                reasoning = "리스크온 환경의 중립 업종"
        elif regime.regime == "risk_off":
            if is_defensive:
                value = 10
                reasoning = "리스크오프 환경에서 방어 업종 우위"
            elif is_offensive:
                value = -15
                reasoning = "리스크오프 환경에서 공격 업종 부담"
            else:
                value = -5
                reasoning = "리스크오프 환경에서 보수적 할인"
        else:
            value = 0
            reasoning = "중립 레짐"

        return FactorScore(value=value, confidence=score_confidence(regime.regime, sector_raw), reasoning=reasoning)
