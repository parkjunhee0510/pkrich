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

        # Look-ahead guard: exclude rows whose signal_date equals today's
        # analysis date. Even if a same-day signal somehow appears with a
        # return attached (pipeline ordering bug, data correction, etc.),
        # we must not let today's decision read a performance signal that
        # was partly produced by today's factors.
        today = str(analysis.date or "").strip()
        if today:
            ticker_signals = [
                item for item in ticker_signals
                if str(item.get("signal_date", item.get("date", ""))).strip() < today
            ]
            if not ticker_signals:
                return FactorScore(value=0, confidence=0.2, reasoning="과거 시그널 이력이 부족")

        evaluated = [item for item in ticker_signals if item.get("return_5d") not in ("", "N/A", None)]
        if not evaluated:
            return FactorScore(value=0, confidence=0.3, reasoning="수익률이 확인된 시그널이 부족")

        wins = sum(1 for item in evaluated if (parse_float(item.get("return_5d", "0")) or 0) > 0)
        win_rate = wins / len(evaluated)
        sample_size = len(evaluated)

        # Center around 50% win rate so neutral history maps to 0.
        # Sample-size scaling keeps a small handful of wins/losses from
        # overpowering fresher factors before enough evidence accumulates.
        centered = (win_rate - 0.5) * 30.0
        sample_scale = min(1.0, sample_size / 5.0)
        value = int(round(max(-10.0, min(10.0, centered * sample_scale))))
        reasoning = f"최근 시그널 승률 {win_rate:.0%} ({wins}/{len(evaluated)})"
        return FactorScore(value=value, confidence=score_confidence(evaluated), reasoning=reasoning)
