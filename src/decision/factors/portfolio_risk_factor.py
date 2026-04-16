from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class PortfolioRiskFactor(DecisionFactor):
    name = "portfolio_risk"
    description = "포트폴리오 섹터 집중과 고상관 클러스터 위험"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del regime
        portfolio_risk = signal_stats.get("_portfolio_risk", {}) if isinstance(signal_stats, dict) else {}
        if not isinstance(portfolio_risk, dict):
            return FactorScore(value=0, confidence=0.2, reasoning="포트폴리오 리스크 데이터가 없어 감점하지 않음")

        sector = (
            analysis.data_snapshot.get("Sector")
            or analysis.fundamentals.get("sector")
            or (collected.sector if collected else "")
            or "Unknown"
        )
        sector_exposure = portfolio_risk.get("sector_exposure", {})
        if not isinstance(sector_exposure, dict):
            sector_exposure = {}
        sector_weight = float(sector_exposure.get(sector, 0.0) or 0.0)

        score = 0
        reasons: list[str] = []
        if sector_weight >= 45:
            score -= 6
            reasons.append(f"{sector} 섹터 비중 {sector_weight:.1f}%로 과집중 상태")
        elif sector_weight >= 30:
            score -= 3
            reasons.append(f"{sector} 섹터 비중 {sector_weight:.1f}%로 다소 높은 편")

        correlations = portfolio_risk.get("correlation_pairs", [])
        if isinstance(correlations, list) and sector_weight >= 30:
            has_high_corr = any(
                isinstance(pair, dict)
                and analysis.ticker in {pair.get("ticker_1"), pair.get("ticker_2")}
                for pair in correlations
            )
            if has_high_corr:
                score -= 3
                reasons.append("같은 포트폴리오 내 고상관 종목과 함께 움직일 가능성이 큼")

        if score == 0:
            return FactorScore(value=0, confidence=0.8, reasoning="현재 포트폴리오 집중 리스크 감점 요인은 크지 않음")
        confidence = 0.9 if sector_weight >= 30 else 0.7
        return FactorScore(value=score, confidence=confidence, reasoning=" / ".join(reasons))
