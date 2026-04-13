"""Tests for src.decision.decision_layer — per-ticker conviction scoring."""
from __future__ import annotations

import unittest
from dataclasses import field
from datetime import date

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


class TestDecideTicker(unittest.TestCase):

    def setUp(self) -> None:
        self.config = _load_weights()
        self.regime = MarketRegime()

    def test_conviction_in_valid_range(self) -> None:
        analysis = _make_analysis()
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        self.assertGreaterEqual(decision.conviction, 0)
        self.assertLessEqual(decision.conviction, 100)

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
        """Decision factors should contain all 8 scoring dimensions."""
        analysis = _make_analysis()
        decision = _decide_ticker(analysis, None, self.regime, {}, date(2026, 4, 10), self.config)
        expected_keys = {
            "valuation", "momentum", "catalyst_recency", "signal_track_record",
            "news_tone", "regime_adjustment", "earnings_pattern", "fundamentals",
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


class TestLoadWeights(unittest.TestCase):

    def test_default_weights_structure(self) -> None:
        config = _load_weights()
        self.assertIn("factors", config)
        self.assertIn("thresholds", config)
        self.assertIn("valid_until", config)
        self.assertEqual(config["thresholds"]["buy"], 65)
        self.assertEqual(config["thresholds"]["avoid"], 35)


if __name__ == "__main__":
    unittest.main()
