from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.prompts import PromptContext, get_prompt_template


class PromptTemplateTests(unittest.TestCase):
    def test_prompt_versions_define_all_llm_modules(self) -> None:
        module_names = {
            "news_analysis_module",
            "research_narrative_module",
            "risk_assessment_module",
            "signal_takeaway_module",
            "weekly_insight_module",
        }
        for version in ("research_v1", "research_v2"):
            for module_name in module_names:
                template = get_prompt_template(version, module_name)
                self.assertEqual(template.version, version)
                self.assertEqual(template.name, module_name)

    def test_render_methods_return_non_empty_text(self) -> None:
        template = get_prompt_template("research_v1", "news_analysis_module")
        ctx = PromptContext(run_date=date(2026, 4, 16))

        system_text = template.render_system(ctx)
        user_text = template.render_user([{"ticker": "AAPL", "news": []}], ctx)

        self.assertTrue(system_text.strip())
        self.assertTrue(user_text.strip())
        self.assertIn("AAPL", user_text)

    def test_validate_response_accepts_valid_shape_and_rejects_invalid_shape(self) -> None:
        template = get_prompt_template("research_v1", "signal_takeaway_module")
        valid = {
            "tickers": [
                {
                    "ticker": "AAPL",
                    "signal_or_takeaway": "매수 관찰 — 실적 기대 | 진입 트리거 200 돌파 | 목표 210/220 | 손절 194",
                }
            ]
        }
        invalid = {
            "tickers": [
                {
                    "ticker": "AAPL",
                    "signal_or_takeaway": "짧음",
                }
            ]
        }

        self.assertTrue(template.validate_response(valid))
        with self.assertRaises(ValueError):
            template.validate_response(invalid)

    def test_research_narrative_template_renders_peer_rank_context(self) -> None:
        template = get_prompt_template("research_v1", "research_narrative_module")
        ctx = PromptContext(run_date=date(2026, 4, 16))

        user_text = template.render_user(
            [
                {
                    "ticker": "AAPL",
                    "peer_rank": {
                        "per_pctl": 25,
                        "rs_pctl": 78,
                        "roe_pctl": 60,
                        "revenue_growth_pctl": 55,
                        "summary": "PER 하위 25% (저평가), 모멘텀 상위 22%",
                    },
                }
            ],
            ctx,
        )

        self.assertIn("peer_rank", user_text)
        self.assertIn("25", user_text)
        self.assertIn("78", user_text)

    def test_weekly_insight_template_validates_structured_report(self) -> None:
        template = get_prompt_template("research_v1", "weekly_insight_module")
        valid = {
            "headline": "2026-W16 주간 리포트",
            "summary": "시장 환경과 주요 종목 변화를 요약합니다. 다음 주 리스크와 액션 플랜도 함께 정리합니다.",
            "market_environment": {"summary": "위험선호가 완만히 개선됐습니다.", "details": ["VIX 안정", "기술주 상대강세"]},
            "top_movers": {
                "summary": "주간 변동이 컸던 종목입니다.",
                "items": [
                    {
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "weekly_change": "+5.0%",
                        "catalyst": "AI 기대",
                        "decision_change": "buy (68)",
                    }
                ],
            },
            "signal_review": {"summary": "bull 시그널 성과가 우세했습니다.", "details": ["bull 5D win rate +60%"]},
            "risk_points": {"summary": "다음 주 CPI 전 변동성 확대 가능성", "items": ["CPI 발표"]},
            "next_week_action_plan": {"summary": "conviction 상위 종목 중심 점검", "items": ["AAPL 실적 확인"]},
            "portfolio_suggestions": {"summary": "포트폴리오 집중도 점검이 필요합니다.", "items": ["기술주 비중 점검"]},
        }
        self.assertTrue(template.validate_response(valid))


if __name__ == "__main__":
    unittest.main()
