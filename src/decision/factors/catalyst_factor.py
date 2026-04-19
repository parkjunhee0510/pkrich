from __future__ import annotations

from datetime import date

from src.decision.base import DecisionFactor, FactorScore
from src.decision.factors._shared import parse_int, score_confidence
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


class CatalystFactor(DecisionFactor):
    name = "catalyst_recency"
    description = "실적 및 하드 촉매의 근접성"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict,
    ) -> FactorScore:
        del collected, regime, signal_stats
        run_date = _parse_date(analysis.date)
        score = 0.0
        earnings_detail = ""

        for event in analysis.upcoming_events:
            if event.get("type") == "earnings":
                days_until = parse_int(event.get("days_until"))
                if days_until is not None:
                    earnings_detail = f"실적 D-{days_until}"
                    if days_until <= 3:
                        score += 12
                    elif days_until <= 7:
                        score += 8
                    elif days_until <= 14:
                        score += 3
                    break

        sec_detail = ""
        for ref in analysis.news_references:
            if ref.catalyst_type == "hard" and ref.published_at:
                try:
                    pub_date = date.fromisoformat(ref.published_at[:10])
                except ValueError:
                    continue
                if run_date is None:
                    age_days = 0
                else:
                    age_days = (run_date - pub_date).days
                if age_days < 0:
                    continue
                sec_detail = f"하드 촉매 {ref.published_at[:10]}"
                if age_days <= 3:
                    score += 6
                elif age_days <= 7:
                    score += 4
                elif age_days <= 14:
                    score += 2
                break

        if score == 0:
            score = -5

        confidence = score_confidence(analysis.upcoming_events, analysis.news_references)
        reasoning = " / ".join(part for part in [earnings_detail, sec_detail] if part) or "가까운 촉매가 없어 감점"
        return FactorScore(value=int(round(max(-10, min(20, score)))), confidence=confidence, reasoning=reasoning)


def _parse_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(str(raw_value)[:10])
    except ValueError:
        return None
