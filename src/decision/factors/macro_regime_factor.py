"""Macro regime × sector tilt factor.

Scores a ticker based on how its GICS-like sector is expected to perform in
the currently detected market regime. Complements MacroEventFactor (which only
activates when a specific shock event is present) by providing a baseline
"regime tilt" even on quiet days.
"""
from __future__ import annotations

from typing import Any

from src.decision.base import DecisionFactor, FactorScore
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


# sector_key -> regime -> score in [min, max] window configured in yaml.
# Keys are lower-cased substrings we match against the ticker's sector string.
_SECTOR_REGIME_MATRIX: dict[str, dict[str, int]] = {
    "technology": {
        "risk_on": 5, "risk_off": -4, "reflation": 1, "defensive_bias": -5, "neutral": 1,
    },
    "communication": {
        "risk_on": 4, "risk_off": -3, "reflation": 1, "defensive_bias": -3, "neutral": 1,
    },
    "consumer discretionary": {
        "risk_on": 5, "risk_off": -5, "reflation": 3, "defensive_bias": -4, "neutral": 0,
    },
    "consumer cyclical": {
        "risk_on": 5, "risk_off": -5, "reflation": 3, "defensive_bias": -4, "neutral": 0,
    },
    "financial": {
        "risk_on": 3, "risk_off": -2, "reflation": 6, "defensive_bias": -2, "neutral": 0,
    },
    "industrial": {
        "risk_on": 4, "risk_off": -3, "reflation": 6, "defensive_bias": -3, "neutral": 0,
    },
    "energy": {
        "risk_on": 2, "risk_off": -2, "reflation": 7, "defensive_bias": -1, "neutral": 0,
    },
    "material": {
        "risk_on": 3, "risk_off": -3, "reflation": 6, "defensive_bias": -3, "neutral": 0,
    },
    "utilit": {
        "risk_on": -3, "risk_off": 3, "reflation": -3, "defensive_bias": 5, "neutral": 0,
    },
    "staples": {
        "risk_on": -3, "risk_off": 4, "reflation": -2, "defensive_bias": 5, "neutral": 0,
    },
    "consumer defensive": {
        "risk_on": -3, "risk_off": 4, "reflation": -2, "defensive_bias": 5, "neutral": 0,
    },
    "health": {
        "risk_on": 0, "risk_off": 2, "reflation": 0, "defensive_bias": 3, "neutral": 0,
    },
    "real estate": {
        "risk_on": 2, "risk_off": -2, "reflation": -2, "defensive_bias": 3, "neutral": 0,
    },
}


class MacroRegimeFactor(DecisionFactor):
    name = "macro_regime"
    description = "섹터 × 거시 레짐 조합 기반의 구조적 편향 점수"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict[str, Any],
    ) -> FactorScore:
        del signal_stats
        sector = str(
            analysis.data_snapshot.get("Sector")
            or (collected.sector if collected is not None else "")
            or ""
        ).strip().lower()
        if not sector:
            return FactorScore(value=0, confidence=0.3, reasoning="섹터 정보 부족")

        regime_name = (regime.regime or "neutral") if regime else "neutral"
        matrix_row = _match_sector_row(sector)
        if matrix_row is None:
            return FactorScore(
                value=0,
                confidence=0.35,
                reasoning=f"섹터 '{sector}'에 대한 레짐 매트릭스 미정의",
            )

        raw = int(matrix_row.get(regime_name, matrix_row.get("neutral", 0)))
        confidence = 0.7 if regime_name != "neutral" else 0.5
        reasoning = f"{regime_name} 레짐에서 {sector} 섹터 편향 {raw:+d}"
        return FactorScore(value=raw, confidence=confidence, reasoning=reasoning)


def _match_sector_row(sector_lower: str) -> dict[str, int] | None:
    for key, row in _SECTOR_REGIME_MATRIX.items():
        if key in sector_lower:
            return row
    return None
