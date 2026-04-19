from __future__ import annotations

import unittest

from src.analyzer.modules.weekly_insight_module import (
    _normalize_weekly_report,
    build_fallback_weekly_report,
)
from src.analyzer.prompts import get_prompt_template
from src.analyzer.prompts.base import PromptContext


class WeeklyInsightModuleTests(unittest.TestCase):
    def test_missing_headline_is_backfilled_before_schema_validation(self) -> None:
        weekly_inputs = {
            "iso_year": 2026,
            "iso_week": 16,
            "market_moves": [],
            "sector_performance": [],
            "top_movers": [],
            "signal_summary": [],
            "portfolio_risk": {},
            "top_conviction_items": [],
            "next_macro_events": [],
            "action_items": [],
            "market_environment_details": [],
        }
        fallback = build_fallback_weekly_report(weekly_inputs)
        payload = {
            "summary": "이번 주 시장은 실적 기대와 섹터 순환이 혼재했습니다.",
            "market_environment": {"summary": "위험선호 환경", "details": ["SPY +1.2%"]},
            "top_movers": {"summary": "AAPL 중심 상승", "items": []},
            "signal_review": {"summary": "시그널 성과는 혼조", "details": ["bull 3건, bear 1건"]},
            "risk_points": {"summary": "다음 주 CPI 확인", "items": ["2026-04-22 CPI"]},
            "next_week_action_plan": {"summary": "상단 저항 확인", "items": ["AAPL 저항 돌파 확인"]},
            "portfolio_suggestions": {"summary": "포지션 사이즈 유지", "items": ["기존 비중 유지"]},
        }

        normalized = _normalize_weekly_report(payload, fallback)
        prompt = get_prompt_template("research_v2", "weekly_insight_module")
        self.assertTrue(prompt.validate_response(normalized))
        self.assertEqual(normalized["headline"], "2026-W16 주간 리포트")
        self.assertEqual(normalized["summary"], "이번 주 시장은 실적 기대와 섹터 순환이 혼재했습니다.")


if __name__ == "__main__":
    unittest.main()
