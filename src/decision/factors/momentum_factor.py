from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_float, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class MomentumFactor(DecisionFactor):
    name = "momentum"
    description = "RS, 섹터 상대강도, 이동평균, 거래량 기반 모멘텀"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime, signal_stats
        score = 10.0
        pa = analysis.price_action

        rs = parse_float(pa.get("rs_vs_spy"))
        if rs is not None:
            if rs >= 5:
                score += 5
            elif rs >= 2:
                score += 3
            elif rs <= -5:
                score -= 5
            elif rs <= -2:
                score -= 3

        sector_rs = parse_float(pa.get("rs_vs_sector_etf"))
        if sector_rs is not None:
            if sector_rs >= 5:
                score += 4
            elif sector_rs >= 2:
                score += 2
            elif sector_rs <= -5:
                score -= 4
            elif sector_rs <= -2:
                score -= 2

        vs_sma50 = parse_float(pa.get("price_vs_sma50"))
        vs_sma200 = parse_float(pa.get("price_vs_sma200"))
        if vs_sma50 is not None and vs_sma200 is not None:
            if vs_sma50 > 0 and vs_sma200 > 0:
                score += 3
            elif vs_sma50 < 0 and vs_sma200 < 0:
                score -= 3

        rvol = parse_float(pa.get("relative_volume"))
        if rvol is not None and rvol >= 1.3:
            score += 2

        score = max(0, min(20, score))
        confidence = score_confidence(rs, sector_rs, vs_sma50, vs_sma200, rvol)
        reasoning_parts: list[str] = []
        if sector_rs is not None:
            reasoning_parts.append(f"섹터 대비 {sector_rs:+.1f}%")
        if rs is not None:
            reasoning_parts.append(f"SPY 대비 {rs:+.1f}%")
        if vs_sma50 is not None and vs_sma200 is not None:
            if vs_sma50 > 0 and vs_sma200 > 0:
                reasoning_parts.append("SMA50·SMA200 위")
            elif vs_sma50 < 0 and vs_sma200 < 0:
                reasoning_parts.append("SMA50·SMA200 아래")
        if rvol is not None and rvol >= 1.3:
            reasoning_parts.append(f"상대 거래량 {rvol:.2f}배")
        reasoning = " / ".join(reasoning_parts) if reasoning_parts else "모멘텀 데이터가 제한적이라 중립 반영"
        return FactorScore(value=int(round(score)), confidence=confidence, reasoning=reasoning)
