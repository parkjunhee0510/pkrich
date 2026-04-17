from __future__ import annotations

from src.decision.base import DecisionFactor, FactorScore
from src.decision.config import multiplier_for


class ConvictionScorer:
    def __init__(
        self,
        factors: list[DecisionFactor],
        regime_multipliers: dict[str, dict[str, float]] | None = None,
    ) -> None:
        if not factors:
            raise ValueError("At least one factor is required")
        self.factors = factors
        self.regime_multipliers = regime_multipliers or {"risk_on": {}, "risk_off": {}, "neutral": {}}

    def calculate(self, factor_scores_by_name: dict[str, FactorScore], regime_name: str) -> int:
        weighted_min, weighted_max = self._weighted_bounds(regime_name)
        if weighted_max <= weighted_min:
            raise ValueError("Invalid factor ranges for conviction scoring")
        weighted_raw = sum(self.weighted_values(factor_scores_by_name, regime_name).values())
        conviction = int((weighted_raw - weighted_min) / (weighted_max - weighted_min) * 100)
        return max(0, min(100, conviction))

    def weighted_values(self, factor_scores_by_name: dict[str, FactorScore], regime_name: str) -> dict[str, float]:
        weighted: dict[str, float] = {}
        for factor in self.factors:
            score = factor_scores_by_name[factor.name]
            weighted[factor.name] = score.value * multiplier_for(factor.name, regime_name, self.regime_multipliers)
        return weighted

    def _weighted_bounds(self, regime_name: str) -> tuple[float, float]:
        weighted_min = 0.0
        weighted_max = 0.0
        for factor in self.factors:
            multiplier = multiplier_for(factor.name, regime_name, self.regime_multipliers)
            weighted_min += factor.weight_range[0] * multiplier
            weighted_max += factor.weight_range[1] * multiplier
        return weighted_min, weighted_max
