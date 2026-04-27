import unittest

from src.decision.factors.policy_tailwind_factor import PolicyTailwindFactor
from src.types import CollectedTickerData, MarketRegime, TickerAnalysis, TickerImpact


def _analysis(ticker="NVDA"):
    return TickerAnalysis(
        ticker=ticker,
        name=ticker,
        date="2026-04-27",
        summary="",
        key_news=[],
        news_references=[],
        financial_highlights=[],
        risks_or_watchpoints=[],
        signal_or_takeaway="",
        data_snapshot={},
    )


def _collected(ticker="NVDA"):
    return CollectedTickerData(
        ticker=ticker,
        name=ticker,
        sector="technology",
        price=100.0,
        change_percent=0.0,
        currency="USD",
        market_cap="N/A",
        pe_ratio="N/A",
        summary_note="",
    )


def _regime():
    return MarketRegime()


class TestPolicyTailwindFactor(unittest.TestCase):
    def setUp(self):
        self.factor = PolicyTailwindFactor()
        # Mirror what FactorRegistry.discover sets from decision_weights.yaml.
        self.factor.weight_range = (-8, 8)

    def test_zero_when_no_tailwind_data(self):
        score = self.factor.score(_analysis(), _collected(), _regime(), {})
        self.assertEqual(score.value, 0)
        self.assertLess(score.confidence, 0.5)

    def test_negative_tailwind_yields_negative_value(self):
        signal_stats = {
            "_policy_tailwind_scores": {"NVDA": -0.8},
            "_policy_impacts_by_ticker": {
                "NVDA": [
                    TickerImpact("NVDA", "negative", "direct", -0.8, 0.9,
                                 "China revenue exposure"),
                ]
            },
        }
        score = self.factor.score(_analysis(), _collected(), _regime(), signal_stats)
        self.assertEqual(score.value, round(-0.8 * 8))  # = -6
        self.assertGreaterEqual(score.confidence, 0.6)
        self.assertIn("China", score.reasoning)

    def test_positive_tailwind_yields_positive_value(self):
        signal_stats = {
            "_policy_tailwind_scores": {"INTC": 0.5},
            "_policy_impacts_by_ticker": {
                "INTC": [TickerImpact("INTC", "positive", "indirect",
                                      0.4, 0.7, "CHIPS Act subsidy")],
            },
        }
        score = self.factor.score(
            _analysis(ticker="INTC"), _collected(ticker="INTC"),
            _regime(), signal_stats,
        )
        self.assertEqual(score.value, round(0.5 * 8))  # = 4
        self.assertGreater(score.confidence, 0.4)

    def test_value_clamped_to_weight_range(self):
        signal_stats = {"_policy_tailwind_scores": {"NVDA": -1.5}}
        score = self.factor.score(_analysis(), _collected(), _regime(),
                                  signal_stats)
        self.assertEqual(score.value, -8)

    def test_factor_registers_via_discover(self):
        from src.decision.registry import build_factor_registry
        config = {
            "valuation": {"max": 20},
            "momentum": {"max": 20},
            "catalyst_recency": {"min": -10, "max": 20},
            "signal_track_record": {"min": -10, "max": 15},
            "news_tone": {"min": -5, "max": 10},
            "regime_adjustment": {"min": -15, "max": 15},
            "earnings_pattern": {"min": -10, "max": 10},
            "fundamentals": {"max": 10},
            "macro_event": {"min": -8, "max": 6},
            "peer_rank": {"min": -4, "max": 8},
            "portfolio_risk": {"min": -10, "max": 0},
            "macro_regime": {"min": -6, "max": 8},
            "policy_tailwind": {"min": -8, "max": 8},
        }
        registry = build_factor_registry(config)
        self.assertIn("policy_tailwind", registry.names())


if __name__ == "__main__":
    unittest.main()
