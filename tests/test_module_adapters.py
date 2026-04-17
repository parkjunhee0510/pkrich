from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.research_narrative_module import ResearchNarrativeModule
from src.analyzer.modules.trade_frame_module import TradeFrameModule
from src.analyzer.modules.valuation_module import ValuationModule
from src.analyzer.payloads import build_fallback_payloads, build_raw_payloads
from src.types import CollectedTickerData, WatchlistItem
from src.utils.model_config import load_model_profile


def _make_collected() -> CollectedTickerData:
    return CollectedTickerData(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        price=210.0,
        change_percent=1.2,
        currency="USD",
        market_cap="3T",
        pe_ratio="20",
        eps="6.5",
        analyst_target_price="250",
        summary_note="",
        upcoming_events=[{"type": "earnings", "date": "2026-04-30", "days_until": "14"}],
        quarterly_financials=[{"quarter": "2025-Q4", "surprise_pct": "+5.0%", "beat_miss": "beat"}],
        atr_14d="5.0",
        sma_50="205",
        fundamental_metrics={"roe": "30%", "fcf_yield": "4.5%"},
    )


class ModuleAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.watchlist = [WatchlistItem(ticker="AAPL", name="Apple Inc.", sector="Technology")]
        self.collected = {"AAPL": _make_collected()}
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "", "FMP_API_KEY": ""}, clear=False):
            self.raw_payloads = build_raw_payloads(self.watchlist, self.collected, {})
            self.fallback_payloads = build_fallback_payloads(
                self.watchlist,
                self.collected,
                {},
                date(2026, 4, 16),
                raw_payload_by_ticker=self.raw_payloads,
            )
        self.ctx = AnalysisContext(
            watchlist=self.watchlist,
            collected=self.collected,
            news_map={},
            run_date=date(2026, 4, 16),
            model_profile=load_model_profile(),
            available_inputs={"price", "fundamentals", "news", "upcoming_events", "quarterly_financials", "options_summary", "historical_prices"},
            raw_payload_by_ticker=self.raw_payloads,
            fallback_payload_by_ticker=self.fallback_payloads,
            intermediate_results={ticker: dict(payload) for ticker, payload in self.fallback_payloads.items()},
        )

    def test_valuation_module_returns_deterministic_score(self) -> None:
        result = ValuationModule().analyze(self.ctx)
        self.assertIn("valuation_score", result.results_by_ticker["AAPL"])
        self.assertTrue(str(result.results_by_ticker["AAPL"]["valuation_score"]["score"]).endswith("/10"))

    def test_trade_frame_module_returns_trade_frame(self) -> None:
        result = TradeFrameModule().analyze(self.ctx)
        trade_frame = result.results_by_ticker["AAPL"]["trade_frame"]
        self.assertIn("entry_price", trade_frame)
        self.assertIn("stop_loss", trade_frame)

    def test_research_narrative_module_payload_includes_peer_rank(self) -> None:
        ctx = AnalysisContext(
            watchlist=self.watchlist,
            collected=self.collected,
            news_map={},
            run_date=date(2026, 4, 16),
            model_profile=load_model_profile(),
            available_inputs={
                "price",
                "fundamentals",
                "news",
                "upcoming_events",
                "quarterly_financials",
                "options_summary",
                "historical_prices",
                "peer_rank",
            },
            raw_payload_by_ticker=self.raw_payloads,
            fallback_payload_by_ticker=self.fallback_payloads,
            intermediate_results={
                "AAPL": {
                    "valuation_score": {"score": "7/10"},
                    "trade_frame": {"entry_price": "현재가 210"},
                    "news_tone": {"label": "bullish"},
                    "peer_rank": {
                        "per_pctl": 25,
                        "rs_pctl": 78,
                        "summary": "PER 하위 25% (저평가), 모멘텀 상위 22%",
                    },
                }
            },
        )
        payload = ResearchNarrativeModule().build_batch_payload(ctx, ["AAPL"])
        self.assertEqual(payload[0]["peer_rank"]["per_pctl"], 25)
        self.assertEqual(payload[0]["peer_rank"]["rs_pctl"], 78)
