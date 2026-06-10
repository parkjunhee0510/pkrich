from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.utils.macro_event_match import match_macro_events_for_context, score_macro_event_match


class MacroEventMatchTests(unittest.TestCase):
    def test_airline_industry_is_more_negative_than_broad_sector(self) -> None:
        event = {
            "event_type": "hormuz_disruption",
            "severity": "high",
            "summary_ko": "호르무즈 해협 차질로 유가와 물류 변동성이 커질 수 있습니다.",
        }
        score = score_macro_event_match(
            event,
            sector="Industrials",
            industry="Airlines",
        )
        self.assertEqual(score["matched_dimension"], "industry")
        self.assertLess(score["score"], -3)

    def test_defense_industry_receives_positive_middle_east_match(self) -> None:
        event = {
            "event_type": "middle_east_escalation",
            "severity": "high",
            "summary_ko": "중동 확전 우려가 커지고 있습니다.",
        }
        score = score_macro_event_match(
            event,
            sector="Industrials",
            industry="Aerospace & Defense",
        )
        self.assertEqual(score["matched_dimension"], "industry")
        self.assertGreater(score["score"], 0)

    def test_llm_macro_match_filters_unrelated_sector(self) -> None:
        macro_context = {
            "macro_events": [
                {
                    "event_type": "sanctions_escalation",
                    "severity": "medium",
                    "summary_ko": "제재 강화는 반도체와 공급망에 부담입니다.",
                }
            ]
        }
        matched = match_macro_events_for_context(
            macro_context,
            sector="Utilities",
            industry="Water Utilities",
            keywords=["regulated utility"],
        )
        self.assertEqual(matched, [])

    def test_semiconductor_equipment_is_penalized_on_sanctions(self) -> None:
        event = {
            "event_type": "sanctions_escalation",
            "severity": "medium",
            "summary_ko": "제재 강화는 반도체와 공급망에 부담입니다.",
        }
        score = score_macro_event_match(
            event,
            sector="Technology",
            industry="Semiconductor Equipment",
        )
        self.assertEqual(score["matched_dimension"], "industry")
        self.assertLessEqual(score["score"], -5)

    def test_cruise_and_hotel_are_penalized_on_hormuz(self) -> None:
        event = {
            "event_type": "hormuz_disruption",
            "severity": "high",
            "summary_ko": "호르무즈 해협 차질로 유가와 물류 변동성이 커질 수 있습니다.",
        }
        score = score_macro_event_match(
            event,
            sector="Consumer Cyclical",
            industry="Cruise Lines & Hotels",
        )
        self.assertEqual(score["matched_dimension"], "industry")
        self.assertLessEqual(score["score"], -5)

    def test_rail_and_trucking_are_penalized_on_shipping_disruption(self) -> None:
        event = {
            "event_type": "shipping_disruption",
            "severity": "medium",
            "summary_ko": "글로벌 해운 차질이 공급망 부담을 높입니다.",
        }
        score = score_macro_event_match(
            event,
            sector="Industrials",
            industry="Railroad & Trucking",
        )
        self.assertEqual(score["matched_dimension"], "industry")
        self.assertLessEqual(score["score"], -3)

    def test_custom_rules_file_can_add_new_event_type(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rules_path = Path(temp_dir) / "macro_event_rules.yaml"
            rules_path.write_text(
                """
sector_impacts:
  taiwan_blockade:
    technology: -4
industry_rules:
  taiwan_blockade:
    - tokens: ["semiconductor equipment", "lithography"]
      score: -7
      reason: "대만 봉쇄 리스크는 반도체 장비 공급망에 직접 부담입니다."
""".strip(),
                encoding="utf-8",
            )

            score = score_macro_event_match(
                {
                    "event_type": "taiwan_blockade",
                    "severity": "high",
                    "summary_ko": "대만 해협 긴장이 고조되고 있습니다.",
                },
                sector="Technology",
                industry="Semiconductor Equipment",
                rules_path=rules_path,
            )

        self.assertEqual(score["matched_dimension"], "industry")
        self.assertEqual(score["score"], -7)
        self.assertEqual(score["match_reason"], "대만 봉쇄 리스크는 반도체 장비 공급망에 직접 부담입니다.")


if __name__ == "__main__":
    unittest.main()
