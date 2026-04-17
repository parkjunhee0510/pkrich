from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.weekly_insight_module import WeeklyInsightModule


class WeeklyInsightModuleTests(unittest.TestCase):
    def test_module_returns_structured_fallback_without_api_key(self) -> None:
        module = WeeklyInsightModule()
        ctx = AnalysisContext(
            watchlist=[],
            collected={},
            news_map={},
            run_date=date(2026, 4, 16),
            metadata={
                "weekly_inputs": {
                    "iso_year": 2026,
                    "iso_week": 16,
                    "market_moves": [{"label": "S&P 500", "weekly_change": "+1.2%"}],
                    "sector_performance": [{"sector": "Technology", "average_weekly_change": "+2.1%"}],
                    "top_movers": [{
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "weekly_change": "+4.2%",
                        "catalyst": "AI 기대",
                        "decision_change": "buy (68)",
                    }],
                    "signal_summary": ["bull 5D 승률 우세"],
                    "portfolio_risk": {"risk_grade": "B", "recommendations": ["기술주 비중 점검"]},
                    "next_macro_events": [{"date": "2026-04-20", "label": "CPI", "days_until": "4"}],
                    "top_conviction_items": [{"ticker": "AAPL", "action": "buy", "conviction": 68, "catalyst": "실적"}],
                    "market_regime": {"regime": "neutral"},
                }
            },
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            result = module.analyze(ctx)
        report = result.portfolio_result["weekly_report"]

        self.assertIn("market_environment", report)
        self.assertIn("top_movers", report)
        self.assertIn("signal_review", report)
        self.assertIn("risk_points", report)
        self.assertIn("next_week_action_plan", report)
        self.assertIn("portfolio_suggestions", report)
        self.assertTrue(report["summary"])


if __name__ == "__main__":
    unittest.main()
