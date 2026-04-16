from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_float, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class SignalRecordFactor(DecisionFactor):
    name = "signal_track_record"
    description = "최근 시그널 성과 이력"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime
        recent = signal_stats.get("recent_signals", [])
        ticker_signals = [item for item in recent if item.get("ticker") == analysis.ticker]
        if not ticker_signals:
            return FactorScore(value=0, confidence=0.2, reasoning="검증된 시그널 이력이 부족")

        evaluated = [item for item in ticker_signals if item.get("return_5d") not in ("", "N/A", None)]
        if not evaluated:
            return FactorScore(value=0, confidence=0.3, reasoning="수익률이 확인된 시그널이 부족")

        wins = sum(1 for item in evaluated if (parse_float(item.get("return_5d", "0")) or 0) > 0)
        win_rate = wins / len(evaluated)
        if win_rate >= 0.7:
            value = 15
        elif win_rate >= 0.6:
            value = 10
        elif win_rate >= 0.5:
            value = 5
        elif win_rate < 0.3:
            value = -10
        else:
            value = 0
        reasoning = f"최근 시그널 승률 {win_rate:.0%} ({wins}/{len(evaluated)})"
        return FactorScore(value=value, confidence=score_confidence(evaluated), reasoning=reasoning)
