"""Decision factor #9: per-ticker policy tailwind score.

Reads aggregated tailwind scores produced by ``src/analyzer/policy_impact.py``
out of ``signal_stats`` (injected by the pipeline orchestrator) and converts
the [-1.0, +1.0] aggregate into an integer point contribution scaled to this
factor's configured weight range.

When tailwind data is missing for a ticker (e.g. policy stage skipped, or the
ticker had no impacts above the confidence floor), the factor returns a zero
value with low confidence so the decision layer's existing renormalization
treats it as a non-signal.
"""

from __future__ import annotations

from typing import Any

from src.decision.base import DecisionFactor, FactorScore
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis


_POLICY_TAILWIND_KEY = "_policy_tailwind_scores"
_POLICY_IMPACTS_KEY = "_policy_impacts_by_ticker"


class PolicyTailwindFactor(DecisionFactor):
    name = "policy_tailwind"
    description = "정책/규제 이벤트의 종목별 누적 영향(직접/간접 임팩트 합산)"

    def score(
        self,
        analysis: TickerAnalysis,
        collected: CollectedTickerData | None,
        regime: MarketRegime,
        signal_stats: dict[str, Any],
    ) -> FactorScore:
        del collected, regime
        if not isinstance(signal_stats, dict):
            return FactorScore(value=0, confidence=0.3,
                               reasoning="정책 영향 데이터 없음")

        scores = signal_stats.get(_POLICY_TAILWIND_KEY) or {}
        if not isinstance(scores, dict):
            return FactorScore(value=0, confidence=0.3,
                               reasoning="정책 영향 데이터 없음")

        ticker = analysis.ticker
        tailwind = scores.get(ticker)
        if tailwind is None:
            return FactorScore(value=0, confidence=0.3,
                               reasoning="해당 종목 정책 임팩트 미산출")

        try:
            tailwind_f = float(tailwind)
        except (TypeError, ValueError):
            return FactorScore(value=0, confidence=0.3,
                               reasoning="정책 임팩트 형식 오류")

        # Clamp aggregate (defensive — analyzer already clips)
        tailwind_f = max(-1.0, min(1.0, tailwind_f))

        weight_min, weight_max = self.weight_range
        scale = max(abs(weight_min), abs(weight_max)) or 1
        raw_value = int(round(tailwind_f * scale))
        value = max(weight_min, min(weight_max, raw_value))

        impacts_map = signal_stats.get(_POLICY_IMPACTS_KEY) or {}
        impacts = impacts_map.get(ticker, []) if isinstance(impacts_map, dict) else []

        confidence = self._confidence(tailwind_f, impacts)
        reasoning = self._reasoning(tailwind_f, impacts)
        return FactorScore(value=value, confidence=confidence,
                           reasoning=reasoning)

    @staticmethod
    def _confidence(tailwind: float, impacts: list) -> float:
        magnitude = abs(tailwind)
        if not impacts:
            base = 0.4
        else:
            avg_imp_conf = sum(getattr(i, "confidence", 0.5) for i in impacts) / len(impacts)
            base = 0.5 + 0.4 * avg_imp_conf  # 0.5..0.9
        boost = 0.1 if magnitude >= 0.5 else 0.0
        return round(min(0.95, max(0.3, base + boost)), 3)

    @staticmethod
    def _reasoning(tailwind: float, impacts: list) -> str:
        if not impacts:
            sign = "긍정" if tailwind > 0 else "부정" if tailwind < 0 else "중립"
            return f"정책 임팩트 {sign} (집계 {tailwind:+.2f})"
        # Quote the strongest impact's rationale
        top = max(
            impacts,
            key=lambda i: abs(getattr(i, "score", 0.0)) * getattr(i, "confidence", 0.0),
        )
        rationale = (getattr(top, "rationale", "") or "").strip()
        prefix = f"정책 임팩트 {tailwind:+.2f}"
        return f"{prefix} — {rationale}" if rationale else prefix
