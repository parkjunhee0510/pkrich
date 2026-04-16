from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class PeerRankFactor(DecisionFactor):
    name = "peer_rank"
    description = "peer percentile 기반 value-momentum sweet spot"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime, signal_stats
        peer_rank = analysis.peer_rank or {}
        per_pctl = _parse_int(peer_rank.get("per_pctl"))
        rs_pctl = _parse_int(peer_rank.get("rs_pctl"))

        if per_pctl is None or rs_pctl is None:
            return FactorScore(value=0, confidence=0.3, reasoning="peer percentile 데이터가 부족해 중립 반영")

        if per_pctl <= 30 and rs_pctl >= 70:
            return FactorScore(value=8, confidence=0.9, reasoning="섹터 peer 대비 저평가이면서 상대 모멘텀이 강합니다")
        if per_pctl <= 40 and rs_pctl >= 60:
            return FactorScore(value=5, confidence=0.8, reasoning="peer 대비 밸류에이션과 모멘텀이 모두 우호적입니다")
        if rs_pctl <= 30 and per_pctl >= 70:
            return FactorScore(value=-4, confidence=0.8, reasoning="peer 대비 고평가이면서 상대 모멘텀이 약합니다")
        return FactorScore(value=0, confidence=0.7, reasoning="peer percentile 기준 특이 우위는 제한적입니다")


def _parse_int(value: object) -> int | None:
    try:
        if value in ("", None, "N/A"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
