from __future__ import annotations

import unittest

from src.analyzer.research_note import _build_fallback_trade_frame
from src.types import CollectedTickerData


class TradeFrameTests(unittest.TestCase):
    def test_fallback_trade_frame_uses_sma50_for_invalidation(self) -> None:
        market = CollectedTickerData(
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            price=150.0,
            change_percent=1.5,
            currency="USD",
            market_cap="2.50T",
            pe_ratio="25.00",
            summary_note="sample",
            sma_50="145.30",
            upcoming_events=[{"type": "earnings", "label": "실적 발표", "date": "2026-04-30", "days_until": "21"}],
        )

        trade_frame = _build_fallback_trade_frame(market)

        self.assertIn("145.30 USD", trade_frame["invalidation_price"])
        self.assertEqual(trade_frame["watch_period"], "2026-04-30 실적 발표 전까지")

    def test_fallback_trade_frame_defaults_watch_period_when_no_event_exists(self) -> None:
        market = CollectedTickerData(
            ticker="NVDA",
            name="NVIDIA Corp.",
            sector="Semiconductors",
            price=200.0,
            change_percent=-4.0,
            currency="USD",
            market_cap="3.00T",
            pe_ratio="35.00",
            summary_note="sample",
        )

        trade_frame = _build_fallback_trade_frame(market)

        self.assertEqual(trade_frame["watch_period"], "향후 5거래일")
        self.assertIn("반등", trade_frame["bull_scenario"])


if __name__ == "__main__":
    unittest.main()
