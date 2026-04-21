from __future__ import annotations

import os
import sys
import types
import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.weekly_insight_module import WeeklyInsightModule
from src.utils.model_config import load_model_profile


class _FakeWeeklyResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _FakeWeeklyResponsesApi:
    def __init__(self, response: _FakeWeeklyResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeWeeklyOpenAIClient:
    def __init__(self, response: _FakeWeeklyResponse) -> None:
        self.responses = _FakeWeeklyResponsesApi(response)


class WeeklyInsightModuleTests(unittest.TestCase):
    def _weekly_inputs(self) -> dict[str, object]:
        return {
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

    def test_module_returns_structured_fallback_without_api_key(self) -> None:
        module = WeeklyInsightModule()
        ctx = AnalysisContext(
            watchlist=[],
            collected={},
            news_map={},
            run_date=date(2026, 4, 16),
            metadata={"weekly_inputs": self._weekly_inputs()},
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

    def test_module_omits_temperature_for_reasoning_model(self) -> None:
        module = WeeklyInsightModule()
        ctx = AnalysisContext(
            watchlist=[],
            collected={},
            news_map={},
            run_date=date(2026, 4, 16),
            model_profile=load_model_profile(profile_name="economy"),
            metadata={"weekly_inputs": self._weekly_inputs()},
        )
        response_text = (
            '{"headline":"주간 헤드라인","summary":"주간 요약입니다.","market_environment":{"summary":"시장 요약","details":["세부 1"]},'
            '"top_movers":{"summary":"상위 이동 종목","items":[{"ticker":"AAPL","name":"Apple Inc.","weekly_change":"+4.2%","catalyst":"AI 기대","decision_change":"buy (68)"}]},'
            '"signal_review":{"summary":"시그널 점검","details":["승률 우세"]},"risk_points":{"summary":"리스크 요약","items":["CPI 확인"]},'
            '"next_week_action_plan":{"summary":"다음 주 액션","items":["AAPL 추적"]},"portfolio_suggestions":{"summary":"포트폴리오 제안","items":["기술주 비중 점검"]}}'
        )
        fake_client = _FakeWeeklyOpenAIClient(_FakeWeeklyResponse(response_text))
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = lambda api_key=None: fake_client

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False),
            patch.dict(sys.modules, {"openai": fake_openai}),
        ):
            module.analyze(ctx)

        self.assertNotIn("temperature", fake_client.responses.calls[0])


if __name__ == "__main__":
    unittest.main()
