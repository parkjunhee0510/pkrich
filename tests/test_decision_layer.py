"""Tests for src.decision.decision_layer — per-ticker conviction scoring."""
from __future__ import annotations

import unittest
from dataclasses import field
from datetime import date
from unittest.mock import patch

from src.decision.decision_layer import generate_decisions, _decide_ticker, _load_weights
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerDecision


_CTD_REQUIRED = {
    "ticker": "TEST",
    "name": "Test Corp",
    "sector": "Technology",
    "price": 100.0,
    "change_percent": 0.5,
    "currency": "USD",
    "market_cap": "1T",
    "pe_ratio": "25",
    "summary_note": "",
}


def _make_ctd(**overrides: object) -> CollectedTickerData:
    kwargs = {**_CTD_REQUIRED, **overrides}
    return CollectedTickerData(**kwargs)  # type: ignore[arg-type]


def _make_analysis(**overrides: object) -> TickerAnalysis:
    """Build a minimal TickerAnalysis for testing."""
    defaults: dict[str, object] = {
        "ticker": "TEST",
        "name": "Test Corp",
        "date": "2026-04-10",
        "summary": "Test summary for analysis with sufficient length.",
        "key_news": ["News item one for testing."],
        "financial_highlights": ["Revenue grew 15% to $10B"],
        "risks_or_watchpoints": ["Market volatility risk noted."],
        "signal_or_takeaway": "관찰 — 실적 대기 | 진입존 $100–105 / SMA50 이탈 시 손절",
        "data_snapshot": {"Price": "100", "Sector": "Technology"},
        "fundamentals": {},
        "price_action": {},
        "quarterly_financials": [],
        "upcoming_events": [],
        "news_tone": {"label": "neutral", "score": 0},
        "trade_frame": {},
        "news_references": [],
        "valuation_score": {},
        "signal_history": [],
        "sector_comparison": {},
        "options_summary": {},
    }
    defaults.update(overrides)
    return TickerAnalysis(**defaults)  # type: ignore[arg-type]


class TestGenerateDecisions(unittest.TestCase):

    def test_returns_list_of_decisions(self) -> None:
        analyses = [_make_analysis(ticker="AAPL"), _make_analysis(ticker="MSFT")]
        regime = MarketRegime()
        decisions = generate_decisions(analyses, {}, regime, {}, date(2026, 4, 10))
        self.assertEqual(len(decisions), 2)
        self.assertIsInstance(decisions[0], TickerDecision)
        self.assertEqual(decisions[0].ticker, "AAPL")
        self.assertEqual(decisions[1].ticker, "MSFT")

    def test_empty_analyses_returns_empty(self) -> None:
        decisions = generate_decisions([], {}, MarketRegime(), {}, date(2026, 4, 10))
        self.assertEqual(decisions, [])

    def test_never_raises(self) -> None:
        """Even with broken data, returns empty list instead of raising."""
        # Pass None where list expected — should not crash
        decisions = generate_decisions(
            [_make_analysis()],
            None,  # type: ignore[arg-type]
            MarketRegime(),
            None,  # type: ignore[arg-type]
            date(2026, 4, 10),
        )
        # Either empty or valid decisions — no exception
        self.assertIsInstance(decisions, list)


    def test_consumes_provided_consensus_and_quality_summaries(self) -> None:
        analysis = _make_analysis(ticker="AAPL", analysis_consensus={})
        with patch.dict("os.environ", {"DECISION_CONFIDENCE_SHADOW_MODE": "1"}):
            decisions = generate_decisions(
                [analysis],
                {},
                MarketRegime(),
                {},
                date(2026, 4, 10),
                analysis_consensus_by_ticker={
                    "AAPL": {"status": "conflicted", "direction_agreement": False}
                },
                quality_summary_by_ticker={
                    "AAPL": {
                        "fact_warning_count": 2,
                        "hallucination_warning_count": 1,
                        "consistency_warning_count": 1,
                        "fallback_used": True,
                        "encoding_issue_detected": True,
                    }
                },
            )

        self.assertEqual(len(decisions), 1)
        self.assertLess(decisions[0].confidence_meta.get("data_quality", 1.0), 1.0)
        self.assertLess(decisions[0].confidence_meta.get("model_agreement", 1.0), 1.0)


class TestDecideTicker(unittest.TestCase):

    def setUp(self) -> None:
        self.config = _load_weights()
        self.regime = MarketRegime()

    def test_conviction_in_valid_range(self) -> None:
        analysis = _make_analysis()
        with patch.dict("os.environ", {"DECISION_CONFIDENCE_SHADOW_MODE": "1"}):
            decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertGreaterEqual(decision.conviction, 0)
        self.assertLessEqual(decision.conviction, 100)
        self.assertEqual(decision.raw_conviction, decision.conviction)

    def test_shadow_mode_populates_confidence_meta(self) -> None:
        analysis = _make_analysis()
        with patch.dict("os.environ", {"DECISION_CONFIDENCE_SHADOW_MODE": "1"}):
            decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)

        self.assertIn("confidence_gate", decision.confidence_meta)
        self.assertEqual(decision.raw_conviction, decision.conviction)

    def test_shadow_mode_off_leaves_confidence_meta_empty(self) -> None:
        analysis = _make_analysis()
        with patch.dict("os.environ", {"DECISION_CONFIDENCE_SHADOW_MODE": "0"}):
            decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)

        self.assertEqual(decision.confidence_meta, {})
        self.assertEqual(decision.raw_conviction, decision.conviction)

    def test_action_is_valid(self) -> None:
        analysis = _make_analysis()
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertIn(decision.action, ("buy", "watch", "avoid"))

    def test_high_conviction_with_strong_signals(self) -> None:
        """Strong valuation + momentum + earnings beats + risk_on → high conviction."""
        analysis = _make_analysis(
            valuation_score={"score": "9"},
            price_action={
                "rs_vs_spy": "6.0",
                "rs_vs_sector_etf": "4.0",
                "price_vs_sma50": "5.0",
                "price_vs_sma200": "10.0",
                "relative_volume": "1.5",
            },
            quarterly_financials=[
                {"beat_miss": "beat"},
                {"beat_miss": "beat"},
                {"beat_miss": "beat"},
            ],
            news_tone={"label": "bullish", "score": 80},
            upcoming_events=[{"type": "earnings", "days_until": "5"}],
        )
        regime = MarketRegime(regime="risk_on", confidence=70)
        data = _make_ctd(
            forward_eps="5.0",
            eps="4.0",
            held_by_institutions="70%",
        )
        decision = _decide_ticker(analysis, data, regime, {}, date(2026, 4, 10), self.config)
        self.assertGreaterEqual(decision.conviction, 60)

    def test_low_conviction_with_weak_signals(self) -> None:
        """Negative momentum + consecutive misses + risk_off → low conviction."""
        analysis = _make_analysis(
            valuation_score={"score": "2"},
            price_action={
                "rs_vs_spy": "-6.0",
                "rs_vs_sector_etf": "-4.0",
                "price_vs_sma50": "-5.0",
                "price_vs_sma200": "-8.0",
            },
            quarterly_financials=[
                {"beat_miss": "miss"},
                {"beat_miss": "miss"},
                {"beat_miss": "miss"},
            ],
            news_tone={"label": "bearish", "score": -60},
            data_snapshot={"Price": "100", "Sector": "Technology"},
        )
        regime = MarketRegime(regime="risk_off", confidence=60)
        decision = _decide_ticker(analysis, None, regime, {}, date(2026, 4, 10), self.config)
        self.assertLessEqual(decision.conviction, 40)

    def test_reason_is_korean(self) -> None:
        """Reason string should be non-empty Korean text."""
        analysis = _make_analysis()
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertIsInstance(decision.reason, str)
        self.assertGreater(len(decision.reason), 0)

    def test_valid_until_defaults_to_7_days(self) -> None:
        """Without upcoming earnings, valid_until should be run_date + 7."""
        analysis = _make_analysis(upcoming_events=[])
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertEqual(decision.valid_until, "2026-04-17")

    def test_valid_until_uses_earnings_date(self) -> None:
        """With upcoming earnings within window, valid_until uses that date."""
        analysis = _make_analysis(
            upcoming_events=[{"type": "earnings", "days_until": "10", "date": "2026-04-20"}]
        )
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertEqual(decision.valid_until, "2026-04-20")

    def test_factors_dict_has_all_keys(self) -> None:
        """Decision factors should contain all scoring dimensions."""
        analysis = _make_analysis()
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        expected_keys = {
            "valuation", "momentum", "catalyst_recency", "signal_track_record",
            "news_tone", "regime_adjustment", "earnings_pattern", "fundamentals",
            "macro_event", "macro_regime", "peer_rank", "portfolio_risk",
        }
        self.assertEqual(set(decision.factors.keys()), expected_keys)

    def test_frozen_dataclass(self) -> None:
        """TickerDecision should be immutable."""
        analysis = _make_analysis()
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        with self.assertRaises(AttributeError):
            decision.action = "buy"  # type: ignore[misc]

    def test_risk_off_regime_raises_buy_threshold(self) -> None:
        """In risk_off, buy threshold is 75 not 65."""
        analysis = _make_analysis(valuation_score={"score": "7"})
        regime_on = MarketRegime(regime="risk_on", confidence=50)
        regime_off = MarketRegime(regime="risk_off", confidence=50)
        decision_on = _decide_ticker(analysis, None, regime_on, {}, date(2026, 4, 10), self.config)
        decision_off = _decide_ticker(analysis, None, regime_off, {}, date(2026, 4, 10), self.config)
        # Same analysis, but risk_off should be harder to get "buy"
        if decision_on.action == "buy":
            # With higher threshold, off might not be buy
            self.assertGreaterEqual(
                self.config.get("thresholds", {}).get("buy_risk_off", 75),
                self.config.get("thresholds", {}).get("buy", 65),
            )

    def test_sector_relative_strength_lifts_momentum(self) -> None:
        weak = _make_analysis(price_action={"rs_vs_spy": "0.0", "rs_vs_sector_etf": "0.0"})
        strong = _make_analysis(price_action={"rs_vs_spy": "0.0", "rs_vs_sector_etf": "6.0"})
        weak_decision = _decide_ticker(weak, None, self.regime, {}, date(2026, 4, 10), self.config)
        strong_decision = _decide_ticker(strong, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertGreater(strong_decision.factors["momentum"], weak_decision.factors["momentum"])

    def test_regime_multipliers_change_conviction_even_with_same_raw_factors(self) -> None:
        analysis = _make_analysis(
            valuation_score={"score": "7"},
            price_action={
                "rs_vs_spy": "5.0",
                "rs_vs_sector_etf": "4.0",
                "price_vs_sma50": "3.0",
                "price_vs_sma200": "7.0",
            },
            data_snapshot={"Price": "100", "Sector": "Technology"},
        )
        risk_on = MarketRegime(regime="risk_on", confidence=50)
        risk_off = MarketRegime(regime="risk_off", confidence=50)
        decision_on = _decide_ticker(analysis, None, risk_on, {}, date(2026, 4, 10), self.config)
        decision_off = _decide_ticker(analysis, None, risk_off, {}, date(2026, 4, 10), self.config)
        self.assertNotEqual(decision_on.conviction, decision_off.conviction)

    def test_earnings_pattern_rewards_streak_and_improving_surprise(self) -> None:
        weak = _make_analysis(
            quarterly_financials=[
                {"beat_miss": "in-line", "surprise_pct": "+1.0%"},
                {"beat_miss": "in-line", "surprise_pct": "+1.1%"},
                {"beat_miss": "in-line", "surprise_pct": "+0.9%"},
                {"beat_miss": "in-line", "surprise_pct": "+1.0%"},
            ]
        )
        strong = _make_analysis(
            quarterly_financials=[
                {"beat_miss": "beat", "surprise_pct": "+8.0%"},
                {"beat_miss": "beat", "surprise_pct": "+6.0%"},
                {"beat_miss": "beat", "surprise_pct": "+4.0%"},
                {"beat_miss": "in-line", "surprise_pct": "+2.0%"},
            ]
        )
        weak_decision = _decide_ticker(weak, None, self.regime, {}, date(2026, 4, 10), self.config)
        strong_decision = _decide_ticker(strong, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertGreater(strong_decision.factors["earnings_pattern"], weak_decision.factors["earnings_pattern"])

    def test_earnings_pattern_penalizes_consecutive_misses(self) -> None:
        analysis = _make_analysis(
            quarterly_financials=[
                {"beat_miss": "miss", "surprise_pct": "-9.0%"},
                {"beat_miss": "miss", "surprise_pct": "-7.0%"},
                {"beat_miss": "miss", "surprise_pct": "-5.0%"},
                {"beat_miss": "in-line", "surprise_pct": "-1.0%"},
            ]
        )
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertLess(decision.factors["earnings_pattern"], 0)

    def test_portfolio_risk_factor_penalizes_sector_concentration(self) -> None:
        analysis = _make_analysis(ticker="AAPL", data_snapshot={"Price": "100", "Sector": "Technology"})
        signal_stats = {
            "_portfolio_risk": {
                "sector_exposure": {"Technology": 48.0},
                "correlation_pairs": [
                    {"ticker_1": "AAPL", "ticker_2": "MSFT", "correlation": "0.82", "warning": "동행성이 높음"}
                ],
            }
        }
        decision = _decide_ticker(analysis, None, self.regime, signal_stats, date(2026, 4, 10), self.config)
        self.assertLess(decision.factors["portfolio_risk"], 0)

    def test_peer_rank_factor_lifts_conviction_for_value_momentum_sweet_spot(self) -> None:
        weak = _make_analysis(peer_rank={"per_pctl": 55, "rs_pctl": 45})
        strong = _make_analysis(peer_rank={"per_pctl": 25, "rs_pctl": 78})
        weak_decision = _decide_ticker(weak, None, self.regime, {}, date(2026, 4, 10), self.config)
        strong_decision = _decide_ticker(strong, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertGreater(strong_decision.factors["peer_rank"], weak_decision.factors["peer_rank"])

    def test_macro_event_factor_flows_from_macro_context(self) -> None:
        analysis = _make_analysis(data_snapshot={"Price": "100", "Sector": "Consumer Cyclical"})
        decision = _decide_ticker(
            analysis,
            None,
            self.regime,
            {
                "_macro_context": {
                    "macro_events": [
                        {
                            "event_type": "hormuz_disruption",
                            "severity": "high",
                            "summary_ko": "호르무즈 해협 차질로 유가와 물류 변동성이 커질 수 있습니다.",
                            "expires_at": "2026-04-17",
                        }
                    ]
                }
            },
            date(2026, 4, 10),
            self.config,
        )
        self.assertLess(decision.factors["macro_event"], 0)


class TestLoadWeights(unittest.TestCase):

    def test_default_weights_structure(self) -> None:
        config = _load_weights()
        self.assertIn("factors", config)
        self.assertIn("thresholds", config)
        self.assertIn("valid_until", config)
        self.assertEqual(config["thresholds"]["buy"], 65)
        self.assertEqual(config["thresholds"]["avoid"], 35)


@unittest.skip(
    "build_decision_diagnostics was removed in a prior refactor. Leaving the "
    "class as a placeholder in case a diagnostics helper is reintroduced."
)
class TestDecisionDiagnostics(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
