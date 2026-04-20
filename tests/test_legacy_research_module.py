from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.legacy_research_note import LegacyResearchNoteModule
from src.analyzer.research_note import _analysis_from_payload, _run_legacy_analysis_pipeline
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
        pe_ratio="28",
        eps="6.5",
        summary_note="",
        upcoming_events=[{"type": "earnings", "date": "2026-04-30", "days_until": "14"}],
        quarterly_financials=[{"quarter": "2025-Q4", "surprise_pct": "+5.0%", "beat_miss": "beat"}],
        options_summary={"put_call_ratio": "0.8"},
    )


class TestLegacyResearchModule(unittest.TestCase):
    def test_legacy_module_matches_legacy_pipeline_shape(self) -> None:
        watchlist = [WatchlistItem(ticker="AAPL", name="Apple Inc.")]
        collected = {"AAPL": _make_collected()}
        news_map = {}
        model_profile = load_model_profile()
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map=news_map,
            run_date=date(2026, 4, 16),
            model_profile=model_profile,
            available_inputs={"price", "fundamentals", "news", "upcoming_events", "quarterly_financials"},
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            module = LegacyResearchNoteModule()
            result = module.analyze(ctx)
            legacy = _run_legacy_analysis_pipeline(
                watchlist,
                collected,
                news_map,
                date(2026, 4, 16),
                model_profile=model_profile,
            )

        rebuilt = _analysis_from_payload(result.results_by_ticker["AAPL"])
        self.assertEqual(rebuilt.ticker, legacy[0].ticker)
        self.assertEqual(rebuilt.summary, legacy[0].summary)
        self.assertEqual(rebuilt.data_snapshot, legacy[0].data_snapshot)
