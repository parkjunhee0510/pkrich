from __future__ import annotations

import unittest

from src.decision.base import FactorScore
from src.decision.confidence import (
    ConfidenceMeta,
    calculate_confidence_gate,
    calculate_final_conviction,
    evaluate_confidence_meta,
)
from src.types import MarketRegime, TickerAnalysis, TickerDecision


def _make_analysis(**overrides: object) -> TickerAnalysis:
    defaults: dict[str, object] = {
        "ticker": "TEST",
        "name": "Test Corp",
        "date": "2026-04-23",
        "summary": "Test summary",
        "key_news": ["News item"],
        "news_references": [],
        "financial_highlights": ["Revenue grew"],
        "risks_or_watchpoints": ["Margin pressure"],
        "signal_or_takeaway": "Momentum improving with manageable risks.",
        "data_snapshot": {"Price": "100", "Sector": "Technology"},
        "fundamentals": {"pe_ratio": "25", "eps": "4.0"},
        "price_action": {
            "price_vs_sma50": "3.2",
            "price_vs_sma200": "8.1",
            "rs_vs_spy": "2.5",
        },
        "quarterly_financials": [{"beat_miss": "beat"}],
        "upcoming_events": [{"type": "earnings", "days_until": "12"}],
        "news_tone": {"label": "bullish", "score": 0.7},
        "trade_frame": {"bias": "long"},
        "options_summary": {},
        "signal_history": [],
        "sector_comparison": {"relative_strength": "strong"},
        "peer_rank": {"per_pctl": 30, "rs_pctl": 75},
        "valuation_score": {"score": "8"},
        "analysis_consensus": {"status": "agreed", "direction_agreement": True},
        "historical_prices": [],
    }
    defaults.update(overrides)
    return TickerAnalysis(**defaults)  # type: ignore[arg-type]


class TestDecisionConfidence(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = _make_analysis()
        self.regime = MarketRegime(regime="risk_on", confidence=70)
        self.factor_scores = {
            "valuation": FactorScore(value=8, confidence=0.9, reasoning="Valuation is supportive."),
            "momentum": FactorScore(value=10, confidence=0.9, reasoning="Momentum is improving."),
            "news_tone": FactorScore(value=6, confidence=0.8, reasoning="News tone is constructive."),
            "earnings_pattern": FactorScore(value=5, confidence=0.8, reasoning="Earnings trend is solid."),
        }

    def test_confidence_gate_stays_in_range(self) -> None:
        meta = evaluate_confidence_meta(
            analysis=self.analysis,
            regime=self.regime,
            factor_scores_by_name=self.factor_scores,
            macro_context=None,
            portfolio_risk=None,
            analysis_consensus=None,
            quality_summary=None,
        )

        self.assertGreaterEqual(meta.confidence_gate, 0.0)
        self.assertLessEqual(meta.confidence_gate, 1.0)
        self.assertGreaterEqual(calculate_confidence_gate(meta), 0.0)
        self.assertLessEqual(calculate_confidence_gate(meta), 1.0)

    def test_poor_quality_lowers_final_conviction_vs_raw_conviction(self) -> None:
        poor_quality = {
            "missing_critical_fields": 4,
            "critical_field_total": 6,
            "fact_warning_count": 2,
            "hallucination_warning_count": 1,
            "fallback_used": True,
            "encoding_issue_detected": True,
        }
        meta = evaluate_confidence_meta(
            analysis=self.analysis,
            regime=self.regime,
            factor_scores_by_name=self.factor_scores,
            macro_context=None,
            portfolio_risk=None,
            analysis_consensus={"status": "conflicted", "direction_agreement": False},
            quality_summary=poor_quality,
        )

        self.assertLess(calculate_final_conviction(80, meta), 80)

    def test_agreement_and_consistency_improvements_increase_gate(self) -> None:
        weak_meta = evaluate_confidence_meta(
            analysis=_make_analysis(
                signal_or_takeaway="Mixed setup with momentum fading.",
                news_tone={"label": "bearish", "score": -0.7},
                analysis_consensus={"status": "conflicted", "direction_agreement": False, "had_tie_break": True},
            ),
            regime=self.regime,
            factor_scores_by_name={
                "valuation": FactorScore(value=8, confidence=0.9, reasoning="Value is good."),
                "momentum": FactorScore(value=-8, confidence=0.9, reasoning="Momentum is weak."),
            },
            macro_context={"macro_events": [{"severity": "high", "direction": "negative"}]},
            portfolio_risk=None,
            analysis_consensus={"status": "conflicted", "direction_agreement": False, "had_tie_break": True},
            quality_summary=None,
        )
        strong_meta = evaluate_confidence_meta(
            analysis=self.analysis,
            regime=self.regime,
            factor_scores_by_name=self.factor_scores,
            macro_context={"macro_events": [{"severity": "low", "direction": "positive"}]},
            portfolio_risk=None,
            analysis_consensus={"status": "agreed", "direction_agreement": True, "had_tie_break": False},
            quality_summary=None,
        )

        self.assertGreater(strong_meta.evidence_consistency, weak_meta.evidence_consistency)
        self.assertGreater(strong_meta.model_agreement, weak_meta.model_agreement)
        self.assertGreater(strong_meta.confidence_gate, weak_meta.confidence_gate)

    def test_ticker_decision_carries_raw_conviction_and_confidence_meta(self) -> None:
        decision = TickerDecision()

        self.assertEqual(decision.raw_conviction, 0)
        self.assertEqual(decision.confidence_meta, {})

    def test_confidence_meta_serializes_to_expected_keys(self) -> None:
        meta = ConfidenceMeta(
            data_quality=0.8,
            evidence_coverage=0.7,
            evidence_consistency=0.6,
            model_agreement=0.9,
            confidence_gate=0.75,
        )

        self.assertEqual(
            meta.to_dict(),
            {
                "data_quality": 0.8,
                "evidence_coverage": 0.7,
                "evidence_consistency": 0.6,
                "model_agreement": 0.9,
                "confidence_gate": 0.75,
            },
        )


if __name__ == "__main__":
    unittest.main()
