from __future__ import annotations

import unittest

from src.analyzer.validator import ResponseValidator


class ResponseValidatorTests(unittest.TestCase):
    def test_rounding_difference_does_not_warn_or_fallback(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"summary": "목표 가격은 120.40 USD로 봅니다."},
            {"summary": "string"},
            {
                "raw_payload": {"positioning": {"analyst_target_price": "120.00 USD"}},
                "fallback": {"summary": "기본 요약"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "목표 가격은 120.40 USD로 봅니다.")
        self.assertFalse(result.warnings)

    def test_minor_difference_warns_without_fallback(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"summary": "목표 가격은 121.80 USD로 봅니다."},
            {"summary": "string"},
            {
                "raw_payload": {"positioning": {"analyst_target_price": "120.00 USD"}},
                "fallback": {"summary": "기본 요약"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "목표 가격은 121.80 USD로 봅니다.")
        self.assertEqual(result.counts["fact_warning"], 1)

    def test_suspect_difference_replaces_field_on_fact_mismatch(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"summary": "목표 가격은 124.20 USD로 봅니다."},
            {"summary": "string"},
            {
                "raw_payload": {"price": 100.0, "positioning": {"analyst_target_price": "120.00 USD"}},
                "fallback": {"summary": "기본 요약"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "기본 요약")
        self.assertEqual(result.counts["fact_warning"], 1)

    def test_replaces_field_on_fact_mismatch(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"summary": "목표 가격은 999.00 USD로 봅니다."},
            {"summary": "string"},
            {
                "raw_payload": {"price": 100.0, "positioning": {"analyst_target_price": "120.00 USD"}},
                "fallback": {"summary": "기본 요약"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "기본 요약")
        self.assertEqual(result.counts["hallucination_warning"], 1)

    def test_replaces_signal_on_tone_conflict(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 우선 — 반등 기대 | 진입 트리거 100 돌파"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {},
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {"news_tone": {"label": "bearish"}},
            },
        )
        self.assertEqual(result.sanitized_response["signal_or_takeaway"], "중립 관찰")
        self.assertEqual(result.counts["consistency_warning"], 1)

    def test_does_not_treat_context_word_maesu_as_long_direction_token(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "중립 관찰 — 매수 압력 완화 | 진입 트리거 100 확인 | 목표 105/110 | 손절 97"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {},
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {},
            },
        )
        self.assertEqual(
            result.sanitized_response["signal_or_takeaway"],
            "중립 관찰 — 매수 압력 완화 | 진입 트리거 100 확인 | 목표 105/110 | 손절 97",
        )
        self.assertNotIn("fact_warning", result.counts)
        self.assertNotIn("consistency_warning", result.counts)

    def test_replaces_signal_when_targets_are_space_separated_instead_of_slash_delimited(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 관찰 — 실적 기대 | 진입 트리거 273 돌파 | 목표 280 290 | 손절 260"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {},
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["signal_or_takeaway"], "중립 관찰")
        self.assertEqual(result.counts["fact_warning"], 1)

    def test_replaces_signal_when_long_stop_is_outside_current_price_band(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 관찰 — 에너지 가격 반등 | 진입 트리거 149 돌파 | 목표 156/162 | 손절 125"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {"price": 147.68},
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["signal_or_takeaway"], "중립 관찰")
        self.assertEqual(result.counts["fact_warning"], 1)

    def test_replaces_signal_when_target_is_outside_current_price_band(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 관찰 — 실적 기대 반영 | 진입 트리거 102 돌파 | 목표 110/145 | 손절 97"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {"price": 100.0},
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["signal_or_takeaway"], "중립 관찰")
        self.assertEqual(result.counts["fact_warning"], 1)

    def test_replaces_signal_when_target_or_stop_not_in_must_use_values(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 관찰 — 실적 기대 반영 | 진입 트리거 205 회복 | 목표 223/236 | 손절 197"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {
                    "price": 210.0,
                    "price_action": {"atr_14d": "5.0"},
                    "positioning": {"analyst_target_price": "235.00 USD"},
                    "upcoming_events": [{"type": "earnings", "date": "2026-04-30", "days_until": "14"}],
                },
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {
                    "trade_frame": {
                        "entry_price": "205.00",
                        "stop_loss": "198.00",
                        "invalidation_price": "194.00",
                        "target_1": "220.00",
                        "target_2": "235.00",
                    }
                },
            },
        )
        self.assertEqual(result.sanitized_response["signal_or_takeaway"], "중립 관찰")
        self.assertEqual(result.counts["fact_warning"], 2)

    def test_does_not_warn_when_far_stop_is_allowed_support_level(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 관찰 — 실적 기대 반영 | 진입 트리거 360.54 확인 | 목표 378.48/400.00 | 손절 SMA50(235.38 USD)"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {
                    "price": 360.54,
                    "sma_50": "235.38",
                    "sma_200": "210.00",
                    "week52_high": "400.00",
                    "week52_low": "120.00",
                    "price_action": {"atr_14d": "12.00"},
                    "positioning": {"analyst_target_price": "378.48 USD"},
                },
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {
                    "trade_frame": {
                        "target_1": "378.48",
                        "target_2": "400.00",
                        "stop_loss": "235.38",
                        "invalidation_price": "235.38",
                    }
                },
            },
        )

        self.assertEqual(
            result.sanitized_response["signal_or_takeaway"],
            "매수 관찰 — 실적 기대 반영 | 진입 트리거 360.54 확인 | 목표 378.48/400.00 | 손절 SMA50(235.38 USD)",
        )
        self.assertNotIn("fact_warning", result.counts)

    def test_allows_na_target_pair_when_prompt_requests_no_guessing(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"signal_or_takeaway": "매수 관찰 — 근거 부족 | 진입 트리거 N/A | 목표 N/A/N/A | 손절 N/A"},
            {"signal_or_takeaway": "string"},
            {
                "raw_payload": {"price": 100.0},
                "fallback": {"signal_or_takeaway": "중립 관찰"},
                "intermediate": {},
            },
        )

        self.assertEqual(
            result.sanitized_response["signal_or_takeaway"],
            "매수 관찰 — 근거 부족 | 진입 트리거 N/A | 목표 N/A/N/A | 손절 N/A",
        )
        self.assertNotIn("fact_warning", result.counts)

    def test_replaces_key_news_on_unmatched_title_like_item(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"key_news": ["Completely New Headline About Acquisition Talks"]},
            {"key_news": "list"},
            {
                "raw_payload": {"news": [{"title": "Apple AI launch gains traction"}]},
                "fallback": {"key_news": ["기본 뉴스 요약"]},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["key_news"], ["기본 뉴스 요약"])
        self.assertEqual(result.counts["hallucination_warning"], 1)


if __name__ == "__main__":
    unittest.main()
