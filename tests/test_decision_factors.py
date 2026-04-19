from __future__ import annotations

import unittest

from src.decision.factors.earnings_factor import EarningsFactor
from src.decision.factors.catalyst_factor import CatalystFactor
from src.decision.factors.fundamentals_factor import FundamentalsFactor
from src.decision.factors.momentum_factor import MomentumFactor
from src.decision.factors.news_tone_factor import NewsToneFactor
from src.decision.factors.peer_rank_factor import PeerRankFactor
from src.decision.factors.portfolio_risk_factor import PortfolioRiskFactor
from src.decision.factors.signal_record_factor import SignalRecordFactor
from src.types import CollectedTickerData, MarketRegime, NewsItem, TickerAnalysis


def _make_analysis(**overrides):
    defaults = {
        "ticker": "TEST",
        "name": "Test Corp",
        "date": "2026-04-10",
        "summary": "summary long enough for testing module behavior.",
        "key_news": ["news"],
        "financial_highlights": ["Revenue grew 10%"],
        "risks_or_watchpoints": ["risk one"],
        "signal_or_takeaway": "중립 관찰 — 테스트 | 진입 트리거 100 상향 | 목표 105/110 | 손절 97",
        "data_snapshot": {"Price": "100", "Sector": "Technology"},
        "fundamentals": {},
        "price_action": {},
        "quarterly_financials": [],
        "upcoming_events": [],
        "news_tone": {"label": "neutral"},
        "trade_frame": {},
        "news_references": [],
        "valuation_score": {},
        "signal_history": [],
        "sector_comparison": {},
        "options_summary": {},
    }
    defaults.update(overrides)
    return TickerAnalysis(**defaults)


def _make_collected(**overrides):
    defaults = {
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
    defaults.update(overrides)
    return CollectedTickerData(**defaults)


class DecisionFactorTests(unittest.TestCase):
    def test_catalyst_factor_rewards_only_truly_near_earnings(self) -> None:
        factor = CatalystFactor()
        far = _make_analysis(date="2026-04-10", upcoming_events=[{"type": "earnings", "days_until": "23"}])
        near = _make_analysis(date="2026-04-10", upcoming_events=[{"type": "earnings", "days_until": "4"}])
        self.assertLess(factor.score(far, None, MarketRegime(), {}).value, factor.score(near, None, MarketRegime(), {}).value)
        self.assertEqual(factor.score(far, None, MarketRegime(), {}).value, -5)

    def test_catalyst_factor_only_counts_recent_hard_catalysts(self) -> None:
        factor = CatalystFactor()
        stale = _make_analysis(
            date="2026-04-10",
            news_references=[NewsItem(title="8-K", source="SEC", published_at="2026-03-20", catalyst_type="hard")],
        )
        fresh = _make_analysis(
            date="2026-04-10",
            news_references=[NewsItem(title="8-K", source="SEC", published_at="2026-04-08", catalyst_type="hard")],
        )
        self.assertEqual(factor.score(stale, None, MarketRegime(), {}).value, -5)
        self.assertGreater(factor.score(fresh, None, MarketRegime(), {}).value, 0)

    def test_momentum_factor_rewards_sector_relative_strength(self) -> None:
        weak = _make_analysis(price_action={"rs_vs_spy": "0.0", "rs_vs_sector_etf": "0.0"})
        strong = _make_analysis(price_action={"rs_vs_spy": "0.0", "rs_vs_sector_etf": "6.0"})
        factor = MomentumFactor()
        weak_score = factor.score(weak, None, MarketRegime(), {})
        strong_score = factor.score(strong, None, MarketRegime(), {})
        self.assertGreater(strong_score.value, weak_score.value)
        self.assertGreaterEqual(strong_score.confidence, weak_score.confidence)

    def test_earnings_factor_rewards_beat_streak(self) -> None:
        factor = EarningsFactor()
        weak = _make_analysis(quarterly_financials=[{"beat_miss": "in-line", "surprise_pct": "+1.0%"}] * 4)
        strong = _make_analysis(quarterly_financials=[
            {"beat_miss": "beat", "surprise_pct": "+8.0%"},
            {"beat_miss": "beat", "surprise_pct": "+6.0%"},
            {"beat_miss": "beat", "surprise_pct": "+4.0%"},
            {"beat_miss": "in-line", "surprise_pct": "+2.0%"},
        ])
        self.assertGreater(factor.score(strong, None, MarketRegime(), {}).value, factor.score(weak, None, MarketRegime(), {}).value)

    def test_news_tone_factor_penalizes_bearish_tone(self) -> None:
        factor = NewsToneFactor()
        analysis = _make_analysis(news_tone={"label": "bearish"}, price_action={"rs_vs_spy": "-3.0"})
        score = factor.score(analysis, None, MarketRegime(), {})
        self.assertLess(score.value, 0)
        self.assertTrue(score.reasoning)

    def test_signal_record_factor_uses_signal_stats(self) -> None:
        factor = SignalRecordFactor()
        signal_stats = {"recent_signals": [
            {"ticker": "TEST", "return_5d": "+2.0%"},
            {"ticker": "TEST", "return_5d": "+1.5%"},
            {"ticker": "TEST", "return_5d": "-0.5%"},
        ]}
        score = factor.score(_make_analysis(), None, MarketRegime(), signal_stats)
        self.assertGreater(score.value, 0)
        self.assertGreaterEqual(score.confidence, 0.6)

    def test_fundamentals_factor_drops_confidence_when_data_missing(self) -> None:
        factor = FundamentalsFactor()
        score = factor.score(_make_analysis(), None, MarketRegime(), {})
        self.assertLessEqual(score.confidence, 0.3)

    def test_portfolio_risk_factor_penalizes_concentrated_sector(self) -> None:
        factor = PortfolioRiskFactor()
        signal_stats = {
            "_portfolio_risk": {
                "sector_exposure": {"Technology": 46.0},
                "correlation_pairs": [{"ticker_1": "TEST", "ticker_2": "MSFT", "correlation": "0.80", "warning": "고상관"}],
            }
        }
        score = factor.score(_make_analysis(), _make_collected(), MarketRegime(), signal_stats)
        self.assertLess(score.value, 0)
        self.assertTrue(score.reasoning)

    def test_peer_rank_factor_rewards_value_momentum_sweet_spot(self) -> None:
        factor = PeerRankFactor()
        score = factor.score(
            _make_analysis(peer_rank={"per_pctl": 25, "rs_pctl": 78}),
            None,
            MarketRegime(),
            {},
        )
        self.assertGreaterEqual(score.value, 4)
        self.assertGreaterEqual(score.confidence, 0.8)

    def test_peer_rank_factor_penalizes_expensive_weak_momentum(self) -> None:
        factor = PeerRankFactor()
        score = factor.score(
            _make_analysis(peer_rank={"per_pctl": 75, "rs_pctl": 20}),
            None,
            MarketRegime(),
            {},
        )
        self.assertLessEqual(score.value, -4)

    def test_peer_rank_factor_can_score_mixed_case_without_flattening_to_zero(self) -> None:
        factor = PeerRankFactor()
        score = factor.score(
            _make_analysis(peer_rank={"per_pctl": 0, "rs_pctl": 40}),
            None,
            MarketRegime(),
            {},
        )
        self.assertGreater(score.value, 0)


if __name__ == "__main__":
    unittest.main()
