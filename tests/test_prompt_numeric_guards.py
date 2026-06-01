from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.prompts import PromptContext, get_prompt_template


class PromptNumericGuardTests(unittest.TestCase):
    def test_risk_templates_limit_triggers_to_payload_values(self) -> None:
        ctx = PromptContext(run_date=date(2026, 5, 13))
        for version in ("research_v1", "research_v2"):
            template = get_prompt_template(version, "risk_assessment_module")
            user_text = template.render_user([{"ticker": "AMD"}], ctx)

            self.assertIn("가격/날짜/수치 트리거는 payload에 있는 값만 사용", user_text)
            self.assertIn("새 트리거 값을 계산하거나 반올림해 만들지 마세요", user_text)

    def test_narrative_templates_limit_financial_numbers_to_payload_values(self) -> None:
        ctx = PromptContext(run_date=date(2026, 5, 13))
        for version in ("research_v1", "research_v2"):
            template = get_prompt_template(version, "research_narrative_module")
            user_text = template.render_user([{"ticker": "XOM"}], ctx)

            self.assertIn("financial_highlights의 숫자는 payload에 있는 값만 그대로 사용", user_text)
            self.assertIn("새 비율이나 가격을 계산하지 마세요", user_text)


if __name__ == "__main__":
    unittest.main()
