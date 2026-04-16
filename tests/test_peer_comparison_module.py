from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.peer_comparison_module import PeerComparisonModule
from src.analyzer.payloads import build_fallback_payloads, build_raw_payloads
from src.types import CollectedTickerData, WatchlistItem
from src.utils.model_config import load_model_profile
from src.utils.quarterly_financials import extract_latest_revenue_growth


def _collected(
    ticker: str,
    sector: str,
    market_cap: str,
    pe_ratio: str,
    rs_vs_spy: str,
    change_30d: str,
) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=ticker,
        sector=sector,
        price=100.0,
        change_percent=1.0,
        currency="USD",
        market_cap=market_cap,
        pe_ratio=pe_ratio,
        summary_note="",
        price_change_30d=change_30d,
        rs_vs_spy=rs_vs_spy,
        avg_volume_3m="1000000",
        quarterly_financials=[
            {"quarter": "2025-Q4", "revenue": "120.0B"},
            {"quarter": "2025-Q3", "revenue": "118.0B"},
            {"quarter": "2024-Q4", "revenue": "100.0B"},
        ],
        fundamental_metrics={"roe": "20.0%", "gross_margin": "45.0%"},
    )


class PeerComparisonModuleTests(unittest.TestCase):
    def test_builds_sector_comparison_from_peer_candidates(self) -> None:
        watchlist = [WatchlistItem(ticker="AAPL", name="Apple", sector="Technology")]
        collected = {"AAPL": _collected("AAPL", "Technology", "1000", "20.0x", "+4.0%", "+6.0%")}
        raw_payloads = build_raw_payloads(
            watchlist,
            collected,
            {},
            peer_candidates_by_ticker={
                "AAPL": [
                    {"ticker": "MSFT", "market_cap": "1100", "pe_ratio": "30.0x", "roe": "25.0%", "gross_margin": "50.0%", "price_change_30d": "+4.0%"},
                    {"ticker": "GOOG", "market_cap": "900", "pe_ratio": "26.0x", "roe": "22.0%", "gross_margin": "48.0%", "price_change_30d": "+2.0%"},
                    {"ticker": "ORCL", "market_cap": "950", "pe_ratio": "18.0x", "roe": "30.0%", "gross_margin": "60.0%", "price_change_30d": "+1.0%"},
                ]
            },
        )
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map={},
            run_date=date(2026, 4, 16),
            model_profile=load_model_profile(),
            available_inputs={"fundamentals", "historical_prices", "price", "peer_candidates"},
            raw_payload_by_ticker=raw_payloads,
            fallback_payload_by_ticker=build_fallback_payloads(watchlist, collected, {}, date(2026, 4, 16), raw_payload_by_ticker=raw_payloads),
            intermediate_results={},
        )

        result = PeerComparisonModule().analyze(ctx)
        comparison = result.results_by_ticker["AAPL"]["sector_comparison"]
        peer_rank = result.results_by_ticker["AAPL"]["peer_rank"]
        self.assertIn("summary", comparison)
        self.assertEqual(comparison["pe_ratio"]["peer_average"], "24.67x")
        self.assertEqual(result.diagnostics["selected_peers_by_ticker"]["AAPL"]["source"], "finnhub")
        self.assertIn("per_pctl", peer_rank)
        self.assertIn("rs_pctl", peer_rank)
        self.assertIn("summary", peer_rank)

    def test_falls_back_to_watchlist_peers_when_candidates_missing(self) -> None:
        watchlist = [
            WatchlistItem(ticker="AAPL", name="Apple", sector="Technology"),
            WatchlistItem(ticker="MSFT", name="Microsoft", sector="Technology"),
            WatchlistItem(ticker="GOOG", name="Google", sector="Technology"),
        ]
        collected = {
            "AAPL": _collected("AAPL", "Technology", "1000", "20.0x", "+4.0%", "+6.0%"),
            "MSFT": _collected("MSFT", "Technology", "1100", "30.0x", "+3.0%", "+4.0%"),
            "GOOG": _collected("GOOG", "Technology", "900", "26.0x", "+2.0%", "+2.0%"),
        }
        raw_payloads = build_raw_payloads(watchlist, collected, {})
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map={},
            run_date=date(2026, 4, 16),
            model_profile=load_model_profile(),
            available_inputs={"fundamentals", "historical_prices", "price", "peer_candidates"},
            raw_payload_by_ticker=raw_payloads,
            fallback_payload_by_ticker=build_fallback_payloads(watchlist, collected, {}, date(2026, 4, 16), raw_payload_by_ticker=raw_payloads),
            intermediate_results={},
        )

        result = PeerComparisonModule().analyze(ctx)
        comparison = result.results_by_ticker["AAPL"]["sector_comparison"]
        self.assertEqual(comparison["pe_ratio"]["peer_average"], "28.00x")
        self.assertEqual(result.diagnostics["selected_peers_by_ticker"]["AAPL"]["source"], "watchlist_fallback")

    def test_omits_dividend_percentile_when_data_missing(self) -> None:
        watchlist = [WatchlistItem(ticker="AAPL", name="Apple", sector="Technology")]
        collected = {"AAPL": _collected("AAPL", "Technology", "1000", "20.0x", "+4.0%", "+6.0%")}
        raw_payloads = build_raw_payloads(
            watchlist,
            collected,
            {},
            peer_candidates_by_ticker={
                "AAPL": [
                    {"ticker": "MSFT", "market_cap": "1100", "pe_ratio": "30.0x", "roe": "25.0%", "gross_margin": "50.0%"},
                    {"ticker": "GOOG", "market_cap": "900", "pe_ratio": "26.0x", "roe": "22.0%", "gross_margin": "48.0%"},
                ]
            },
        )
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map={},
            run_date=date(2026, 4, 16),
            model_profile=load_model_profile(),
            available_inputs={"fundamentals", "historical_prices", "price", "peer_candidates"},
            raw_payload_by_ticker=raw_payloads,
            fallback_payload_by_ticker=build_fallback_payloads(
                watchlist,
                collected,
                {},
                date(2026, 4, 16),
                raw_payload_by_ticker=raw_payloads,
            ),
            intermediate_results={},
        )

        result = PeerComparisonModule().analyze(ctx)
        peer_rank = result.results_by_ticker["AAPL"]["peer_rank"]
        self.assertNotIn("dividend_yield_pctl", peer_rank)

    def test_uses_quarterly_revenue_yoy_for_revenue_growth_source(self) -> None:
        market = _collected("AAPL", "Technology", "1000", "20.0x", "+4.0%", "+6.0%")
        self.assertEqual(extract_latest_revenue_growth(market.quarterly_financials), "+20.0% YoY")


if __name__ == "__main__":
    unittest.main()
