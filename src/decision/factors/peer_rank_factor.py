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

        value_edge = _centered_value_edge(per_pctl)
        momentum_edge = _centered_momentum_edge(rs_pctl)
        blended = (value_edge * 0.55) + (momentum_edge * 0.65)
        score = int(round(max(-6.0, min(6.0, blended * 6.0))))

        if score >= 4:
            reasoning = "peer 대비 저평가와 상대 모멘텀이 함께 우호적입니다"
        elif score >= 1:
            reasoning = "peer 대비 일부 우위가 확인되지만 강한 sweet spot까지는 아닙니다"
        elif score <= -4:
            reasoning = "peer 대비 밸류에이션 부담과 약한 상대 모멘텀이 함께 나타납니다"
        elif score <= -1:
            reasoning = "peer 대비 상대 우위가 약하거나 일부 부담이 있습니다"
        else:
            reasoning = "peer percentile 기준 뚜렷한 우위나 열위는 제한적입니다"
        confidence = 0.7 + (min(1.0, abs(score) / 6.0) * 0.2)
        return FactorScore(value=score, confidence=round(confidence, 2), reasoning=reasoning)


def _parse_int(value: object) -> int | None:
    try:
        if value in ("", None, "N/A"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _centered_value_edge(per_pctl: int) -> float:
    # Low PER percentile is favorable (cheaper than peers), high percentile unfavorable.
    bounded = max(0, min(100, per_pctl))
    return (50.0 - float(bounded)) / 50.0


def _centered_momentum_edge(rs_pctl: int) -> float:
    # High relative-strength percentile is favorable, low percentile unfavorable.
    bounded = max(0, min(100, rs_pctl))
    return (float(bounded) - 50.0) / 50.0
