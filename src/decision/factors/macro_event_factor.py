from __future__ import annotations

from datetime import date
from typing import Any

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis
from src.utils.macro_event_match import match_macro_events_for_context


class MacroEventFactor(DecisionFactor):
    name = "macro_event"
    description = "거시 충격 이벤트의 업종 및 세부 산업 전이 영향"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict[str, Any],
    ) -> FactorScore:
        del regime
        macro_context = signal_stats.get("_macro_context", {}) if isinstance(signal_stats, dict) else {}
        if not isinstance(macro_context, dict):
            return FactorScore(value=0, confidence=0.3, reasoning="거시 충격 이벤트 데이터 부족")

        sector = str(analysis.data_snapshot.get("Sector") or getattr(collected, "sector", "")).strip()
        industry = ""
        if collected is not None:
            industry = str(collected.fundamental_metrics.get("industry", "")).strip()
        if not sector and not industry:
            return FactorScore(value=0, confidence=0.3, reasoning="업종 정보 부족으로 거시 충격 영향 중립")

        run_date = _analysis_date(analysis)
        matched = [
            event
            for event in match_macro_events_for_context(
                macro_context,
                sector=sector,
                industry=industry,
            )
            if not _is_expired(event, run_date)
        ]
        if not matched:
            return FactorScore(value=0, confidence=0.4, reasoning="현재 거시 충격의 직접 업종 영향은 제한적")

        total = int(round(sum(int(event.get("score", 0)) for event in matched[:3])))
        dominant = max(matched[:3], key=lambda item: abs(int(item.get("score", 0))))
        reasoning = str(dominant.get("match_reason", "")).strip() or str(dominant.get("summary_ko", "")).strip()
        confidence = score_confidence(
            sector,
            industry,
            dominant.get("event_type"),
            dominant.get("matched_dimension"),
            dominant.get("severity"),
        )
        return FactorScore(value=total, confidence=confidence, reasoning=reasoning or "거시 충격 영향 반영")


def _analysis_date(analysis: TickerAnalysis) -> date | None:
    raw = str(getattr(analysis, "date", "")).strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _is_expired(event: dict[str, Any], run_date: date | None) -> bool:
    if run_date is None:
        return False
    raw = str(event.get("expires_at", "")).strip()
    if not raw:
        return False
    try:
        return date.fromisoformat(raw) < run_date
    except ValueError:
        return False
