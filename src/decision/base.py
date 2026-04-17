from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


@dataclass(frozen=True)
class FactorScore:
    value: int
    confidence: float
    reasoning: str


class DecisionFactor(ABC):
    name: str = "decision_factor"
    description: str = ""
    weight_range: tuple[int, int] = (0, 0)

    @abstractmethod
    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict[str, Any],
    ) -> FactorScore:
        raise NotImplementedError
