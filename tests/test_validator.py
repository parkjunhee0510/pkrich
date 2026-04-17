from __future__ import annotations

import unittest

from src.analyzer.validator import ResponseValidator


class ResponseValidatorTests(unittest.TestCase):
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
        self.assertEqual(result.counts["fact_warning"], 1)

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


class HallucinationHardeningTests(unittest.TestCase):
    def test_drops_tainted_summary_when_no_fallback(self) -> None:
        validator = ResponseValidator()
        result = validator.validate(
            {"summary": "목표가 888 USD"},
            {"summary": "string"},
            {
                "raw_payload": {"price": 100.0},
                "fallback": {},
                "intermediate": {},
            },
        )
        # Without fallback, tainted summary must be dropped (empty), not
        # passed through — that was the prior silent-leak failure mode.
        self.assertEqual(result.sanitized_response["summary"], "")
        self.assertGreaterEqual(result.counts.get("dropped_unsupported", 0), 1)

    def test_drops_unsupported_key_news_items_when_no_fallback(self) -> None:
        validator = ResponseValidator()
        real_headline = "Apple AI launch gains traction in enterprise deals"
        hallucinated = "Completely Fabricated Acquisition Talks From Nowhere Specific Corp"
        result = validator.validate(
            {"key_news": [real_headline, hallucinated]},
            {"key_news": "list"},
            {
                "raw_payload": {"news": [{"title": real_headline}]},
                "fallback": {},
                "intermediate": {},
            },
        )
        kept = result.sanitized_response["key_news"]
        self.assertIn(real_headline, kept)
        self.assertNotIn(hallucinated, kept)

    def test_percent_absolute_floor_blocks_near_match(self) -> None:
        validator = ResponseValidator()
        # Real payload only mentions 1%. LLM invents 5%. Relative
        # tolerance alone (10%) would be irrelevant here — absolute floor
        # (0.3pp) is what must catch this.
        result = validator.validate(
            {"summary": "이번 분기 성장률은 5% 수준"},
            {"summary": "string"},
            {
                "raw_payload": {"growth": "1%"},
                "fallback": {"summary": "기본"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "기본")

    def test_percent_near_real_value_passes(self) -> None:
        validator = ResponseValidator()
        # 4.8% vs real 5.0% → 0.2pp absolute diff → within floor → accepted.
        result = validator.validate(
            {"summary": "성장률 4.8% 관측"},
            {"summary": "string"},
            {
                "raw_payload": {"growth": "5.0%"},
                "fallback": {"summary": "기본"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "성장률 4.8% 관측")

    def test_short_overlap_headline_does_not_mask_hallucination(self) -> None:
        validator = ResponseValidator()
        # Two tokens shared ("Apple", "Q3") — below the 3-token minimum, so
        # this should be flagged despite surface similarity.
        result = validator.validate(
            {"key_news": ["Apple Q3 Something Totally Different Entirely New Topic"]},
            {"key_news": "list"},
            {
                "raw_payload": {"news": [{"title": "Apple Q3 earnings"}]},
                "fallback": {"key_news": ["기본 뉴스"]},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["key_news"], ["기본 뉴스"])


class UrlCitationTests(unittest.TestCase):
    def test_fabricated_url_in_summary_replaced_by_fallback(self) -> None:
        validator = ResponseValidator()
        real_url = "https://example.com/real-article"
        fake_url = "https://fabricated.example.net/made-up"
        result = validator.validate(
            {"summary": f"근거는 {fake_url} 참고"},
            {"summary": "string"},
            {
                "raw_payload": {"news": [{"title": "Real article", "link": real_url}]},
                "fallback": {"summary": "기본 요약"},
                "intermediate": {},
            },
        )
        self.assertEqual(result.sanitized_response["summary"], "기본 요약")
        self.assertGreaterEqual(result.counts.get("hallucination_warning", 0), 1)

    def test_known_url_passes_through(self) -> None:
        validator = ResponseValidator()
        real_url = "https://example.com/real-article"
        result = validator.validate(
            {"summary": f"관련 링크: {real_url}"},
            {"summary": "string"},
            {
                "raw_payload": {"news": [{"title": "T", "link": real_url}]},
                "fallback": {"summary": "기본"},
                "intermediate": {},
            },
        )
        # Known URL should not trigger any URL-citation warning — summary stays.
        self.assertIn(real_url, result.sanitized_response["summary"])

    def test_fabricated_url_stripped_when_no_fallback(self) -> None:
        validator = ResponseValidator()
        real_url = "https://example.com/ok"
        fake_url = "https://phony.invalid/x"
        result = validator.validate(
            {"summary": f"{fake_url} 에 따르면 상승"},
            {"summary": "string"},
            {
                "raw_payload": {"news": [{"title": "T", "link": real_url}]},
                "fallback": {},
                "intermediate": {},
            },
        )
        self.assertNotIn(fake_url, result.sanitized_response["summary"])
        self.assertGreaterEqual(result.counts.get("dropped_unsupported", 0), 1)

    def test_trailing_punctuation_does_not_falsely_flag(self) -> None:
        validator = ResponseValidator()
        real_url = "https://example.com/article"
        result = validator.validate(
            {"summary": f"참고 링크({real_url}). 중요."},
            {"summary": "string"},
            {
                "raw_payload": {"news": [{"title": "T", "link": real_url}]},
                "fallback": {"summary": "기본"},
                "intermediate": {},
            },
        )
        # URL wrapped in parens/period — still recognized as known.
        self.assertIn(real_url, result.sanitized_response["summary"])


if __name__ == "__main__":
    unittest.main()
