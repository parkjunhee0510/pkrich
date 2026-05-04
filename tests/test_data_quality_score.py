from __future__ import annotations

import unittest
from datetime import date

from src.decision.data_quality import calculate_data_quality_result
from src.types import CollectedTickerData, NewsItem, TickerAnalysis


def _analysis(**overrides: object) -> TickerAnalysis:
    defaults: dict[str, object] = {
        "ticker": "TEST",
        "name": "Test Corp",
        "date": "2026-05-04",
        "summary": "Useful summary.",
        "key_news": ["Reuters: Test Corp expands margin."],
        "news_references": [
            NewsItem(title="Test Corp expands margin", source="Reuters", published_at="2026-05-04"),
            NewsItem(title="Test Corp launches product", source="AP", published_at="2026-05-04"),
        ],
        "financial_highlights": ["Revenue grew 10%"],
        "risks_or_watchpoints": ["FX risk"],
        "signal_or_takeaway": "Watch for follow-through above support.",
        "data_snapshot": {"Price": "100", "Sector": "Technology"},
        "fundamentals": {"pe_ratio": "22", "eps": "4.1", "market_cap": "100B"},
        "price_action": {"price_vs_sma50": "2.0", "rs_vs_spy": "1.2"},
        "quarterly_financials": [{"revenue": "10B", "eps": "1.20"}],
        "upcoming_events": [],
        "news_tone": {"label": "bullish", "score": 0.6},
        "trade_frame": {},
        "options_summary": {},
        "signal_history": [],
        "sector_comparison": {},
        "peer_rank": {},
        "valuation_score": {},
        "analysis_consensus": {},
        "committee_analysis": {},
        "historical_prices": [{"date": "2026-05-04", "close": "100"}],
    }
    defaults.update(overrides)
    return TickerAnalysis(**defaults)  # type: ignore[arg-type]


def _collected(**overrides: object) -> CollectedTickerData:
    defaults: dict[str, object] = {
        "ticker": "TEST",
        "name": "Test Corp",
        "sector": "Technology",
        "price": 100.0,
        "change_percent": 1.0,
        "currency": "USD",
        "market_cap": "100B",
        "pe_ratio": "22",
        "summary_note": "2026-05-04 기준 yfinance 데이터를 사용해 시장 정보를 정리했습니다.",
        "eps": "4.1",
        "historical_prices": [{"date": "2026-05-04", "close": "100"}],
    }
    defaults.update(overrides)
    return CollectedTickerData(**defaults)  # type: ignore[arg-type]


class DataQualityScoreTests(unittest.TestCase):
    def test_complete_recent_data_scores_high_and_exposes_components(self) -> None:
        result = calculate_data_quality_result(
            analysis=_analysis(),
            data=_collected(),
            run_date=date(2026, 5, 4),
            quality_summary={"fact_warning_count": 0, "fallback_used": False},
            macro_context={"as_of": "2026-05-04", "macro_events": [{"event_type": "rates"}]},
        )

        self.assertGreaterEqual(result.score, 0.8)
        self.assertEqual(result.components["price_freshness"], 1.0)
        self.assertGreater(result.components["source_diversity"], 0.5)
        self.assertGreaterEqual(result.confidence_penalty, 0.0)

    def test_stale_missing_sparse_data_scores_lower(self) -> None:
        result = calculate_data_quality_result(
            analysis=_analysis(
                key_news=[],
                news_references=[],
                fundamentals={},
                financial_highlights=[],
                historical_prices=[{"date": "2026-04-20", "close": "90"}],
            ),
            data=_collected(
                price=None,
                market_cap="N/A",
                pe_ratio="N/A",
                eps="N/A",
                summary_note="시장 데이터를 불러오지 못해 기본값을 사용했습니다.",
                historical_prices=[{"date": "2026-04-20", "close": "90"}],
            ),
            run_date=date(2026, 5, 4),
            quality_summary={
                "fact_warning_count": 2,
                "hallucination_warning_count": 1,
                "fallback_used": True,
                "missing_critical_fields": 4,
                "critical_field_total": 6,
            },
            macro_context={},
        )

        self.assertLess(result.score, 0.65)
        self.assertLess(result.components["price_freshness"], 0.6)
        self.assertLess(result.components["news_coverage"], 0.5)
        self.assertGreater(result.confidence_penalty, 0.1)


if __name__ == "__main__":
    unittest.main()
