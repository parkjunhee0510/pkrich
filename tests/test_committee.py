from __future__ import annotations

import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.analyzer.committee import (
    committee_stance_to_action,
    default_committee_analysis,
    derive_agreement_status,
    run_committee_analysis,
    should_trigger_deep_committee_review,
)
from src.types import NewsItem, TickerAnalysis


def _analysis() -> TickerAnalysis:
    return TickerAnalysis(
        ticker="AAPL",
        name="Apple Inc.",
        date="2026-04-23",
        summary="summary",
        key_news=["news"],
        news_references=[NewsItem(title="news", source="src")],
        financial_highlights=["highlight"],
        risks_or_watchpoints=["risk"],
        signal_or_takeaway="watch",
        data_snapshot={"price": "100"},
    )


class CommitteeAnalysisTests(unittest.TestCase):
    def test_five_level_stance_maps_to_existing_action_scale(self) -> None:
        self.assertEqual(committee_stance_to_action("strong_buy"), "buy")
        self.assertEqual(committee_stance_to_action("BUY"), "buy")
        self.assertEqual(committee_stance_to_action("  watch  "), "watch")
        self.assertEqual(committee_stance_to_action("reduce"), "avoid")
        self.assertEqual(committee_stance_to_action("avoid"), "avoid")

    def test_committee_stance_to_action_normalization_and_fallback(self) -> None:
        self.assertEqual(committee_stance_to_action("  Strong_Buy  "), "buy")
        self.assertEqual(committee_stance_to_action("  BuY  "), "buy")
        self.assertEqual(committee_stance_to_action(None), "watch")

    def test_default_committee_payload_schema_shape(self) -> None:
        payload = default_committee_analysis()

        self.assertEqual(
            set(payload.keys()),
            {"status", "agreement_status", "deep_review_triggered", "deep_review_reasons", "roles"},
        )
        self.assertEqual(payload["status"], "economy_only")
        self.assertEqual(payload["agreement_status"], "aligned")
        self.assertFalse(payload["deep_review_triggered"])
        self.assertEqual(payload["deep_review_reasons"], [])
        self.assertEqual(payload["roles"], {})

    def test_agreement_status_uses_action_synonyms(self) -> None:
        self.assertEqual(
            derive_agreement_status(
                {
                    "growth_analyst": {"stance": "strong_buy"},
                    "value_skeptic": {"stance": "buy"},
                }
            ),
            "aligned",
        )
        self.assertEqual(
            derive_agreement_status(
                {
                    "risk_manager": {"stance": "reduce"},
                    "macro_strategist": {"stance": "avoid"},
                }
            ),
            "aligned",
        )

    def test_deep_review_triggers_on_low_pm_confidence_and_strong_objection_codes(self) -> None:
        payload = {
            "pm_confidence": 0.42,
            "risk_manager": {"strong_objection": True},
            "macro_strategist": {"strong_objection": True},
        }

        triggered = should_trigger_deep_committee_review(payload, pm_threshold=0.55)
        not_triggered = should_trigger_deep_committee_review({"pm_confidence": 0.60}, pm_threshold=0.55)

        self.assertEqual(
            triggered,
            {
                "triggered": True,
                "reason_codes": ["pm_low_confidence", "risk_strong_objection", "macro_strong_objection"],
                "pm_confidence": 0.42,
                "pm_threshold": 0.55,
            },
        )
        self.assertEqual(
            not_triggered,
            {
                "triggered": False,
                "reason_codes": [],
                "pm_confidence": 0.60,
                "pm_threshold": 0.55,
            },
        )

    def test_should_trigger_deep_committee_review_defensive_branches(self) -> None:
        self.assertEqual(
            should_trigger_deep_committee_review(None, pm_threshold=30),
            {
                "triggered": False,
                "reason_codes": ["invalid_committee_payload"],
                "pm_confidence": None,
                "pm_threshold": 30,
            },
        )
        self.assertEqual(
            should_trigger_deep_committee_review({"pm_confidence": "bad"}, pm_threshold=30),
            {
                "triggered": False,
                "reason_codes": ["invalid_pm_confidence"],
                "pm_confidence": "bad",
                "pm_threshold": 30,
            },
        )

    def test_run_committee_analysis_builds_all_role_outputs(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []
        pm_prompts: list[dict[str, object]] = []

        def runner(role: str, profile: str, prompt: dict[str, object]) -> dict[str, object]:
            calls.append((role, profile, prompt))
            if role == "pm":
                pm_prompts.append(prompt)
            return {
                "role": role,
                "profile": profile,
                "stance": "watch",
                "confidence": 0.80 if role == "pm" else 0.60,
                "strong_objection": False,
                "summary": f"{role} summary",
            }

        result = run_committee_analysis(_analysis(), run_role=runner)

        self.assertEqual(
            [call[:2] for call in calls],
            [
                ("growth_analyst", "economy"),
                ("value_skeptic", "economy"),
                ("risk_manager", "economy"),
                ("macro_strategist", "economy"),
                ("pm", "economy"),
            ],
        )
        self.assertEqual(result["status"], "economy_only")
        self.assertEqual(result["agreement_status"], "aligned")
        self.assertFalse(result["deep_review_triggered"])
        self.assertEqual(result["deep_review_reasons"], [])
        self.assertEqual(set(result["roles"].keys()), {"growth_analyst", "value_skeptic", "risk_manager", "macro_strategist", "pm"})
        self.assertEqual(
            set(result["roles"]["pm"].keys()),
            {
                "role",
                "round",
                "profile",
                "stance",
                "action",
                "confidence",
                "strong_objection",
                "summary",
                "valid",
                "invalid_reason",
            },
        )
        self.assertNotIn("prompt", result["roles"]["pm"])
        self.assertNotIn("raw", result["roles"]["pm"])
        self.assertEqual(result["roles"]["pm"]["invalid_reason"], "")
        self.assertEqual(len(pm_prompts), 1)
        self.assertEqual(
            set(pm_prompts[0]["context"]["role_outputs"].keys()),
            {"growth_analyst", "value_skeptic", "risk_manager", "macro_strategist"},
        )
        self.assertEqual(result["roles"]["pm"]["summary"], "pm summary")

    def test_committee_prompt_contract_exposes_required_fields(self) -> None:
        from src.analyzer.committee_prompt import build_pm_prompt

        prompt = build_pm_prompt(
            _analysis(),
            round_name="economy",
            profile_name="economy",
            max_summary_sentences=3,
            role_outputs={},
        )

        self.assertEqual(prompt["contract"]["allowed_stances"], ["strong_buy", "buy", "watch", "reduce", "avoid"])
        self.assertEqual(prompt["contract"]["required_fields"]["growth_analyst"], ["stance", "summary"])
        self.assertEqual(prompt["contract"]["required_fields"]["value_skeptic"], ["stance", "summary"])
        self.assertEqual(
            prompt["contract"]["required_fields"]["risk_manager"],
            ["stance", "summary", "strong_objection"],
        )
        self.assertEqual(
            prompt["contract"]["required_fields"]["macro_strategist"],
            ["stance", "summary", "strong_objection"],
        )
        self.assertEqual(prompt["contract"]["required_fields"]["pm"], ["stance", "summary", "confidence"])

    def test_committee_prompt_requires_korean_summary_values(self) -> None:
        from src.analyzer.committee_prompt import build_growth_analyst_prompt

        prompt = build_growth_analyst_prompt(
            _analysis(),
            round_name="economy",
            profile_name="economy",
            max_summary_sentences=2,
            role_outputs={},
        )

        self.assertIn("summary 값은 반드시 한국어", prompt["system"])
        self.assertIn("JSON key는 영어", prompt["system"])
        self.assertIn("summary는 한국어로 작성", prompt["user"])

    def test_run_committee_analysis_reruns_only_risk_macro_pm_when_escalated(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []
        pm_prompts: list[dict[str, object]] = []

        def runner(role: str, profile: str, prompt: dict[str, object]) -> dict[str, object]:
            calls.append((role, profile, prompt))
            if role == "pm":
                pm_prompts.append(prompt)
            if profile == "economy":
                if role == "risk_manager":
                    return {
                        "role": role,
                        "profile": profile,
                        "stance": "watch",
                        "confidence": 0.58,
                        "strong_objection": True,
                        "summary": "risk econ",
                    }
                if role == "pm":
                    return {
                        "role": role,
                        "profile": profile,
                        "stance": "watch",
                        "confidence": 0.42,
                        "strong_objection": False,
                        "summary": "pm econ",
                    }
                return {
                    "role": role,
                    "profile": profile,
                    "stance": "watch",
                    "confidence": 0.60,
                    "strong_objection": False,
                    "summary": f"{role} econ",
                }
            if role in {"risk_manager", "macro_strategist"}:
                return {
                    "role": role,
                    "profile": profile,
                    "stance": "reduce",
                    "confidence": 0.72,
                    "strong_objection": False,
                    "summary": f"{role} deep",
                }
            return {
                "role": role,
                "profile": profile,
                "stance": "watch",
                "confidence": 0.70,
                "strong_objection": False,
                "summary": "pm deep",
            }

        result = run_committee_analysis(_analysis(), run_role=runner)

        self.assertEqual(   
            [call[:2] for call in calls],
            [
                ("growth_analyst", "economy"),
                ("value_skeptic", "economy"),
                ("risk_manager", "economy"),
                ("macro_strategist", "economy"),
                ("pm", "economy"),
                ("risk_manager", "deep"),
                ("macro_strategist", "deep"),
                ("pm", "deep"),
            ],
        )
        self.assertEqual(result["status"], "deep_reviewed")
        self.assertTrue(result["deep_review_triggered"])
        self.assertEqual(result["deep_review_reasons"], ["pm_low_confidence", "risk_strong_objection"])
        self.assertEqual(result["agreement_status"], "mixed")
        self.assertEqual(len(pm_prompts), 2)
        self.assertEqual(
            set(pm_prompts[0]["context"]["role_outputs"].keys()),
            {"growth_analyst", "value_skeptic", "risk_manager", "macro_strategist"},
        )
        self.assertEqual(
            set(pm_prompts[1]["context"]["role_outputs"].keys()),
            {"growth_analyst", "value_skeptic", "risk_manager", "macro_strategist"},
        )
        self.assertEqual(pm_prompts[1]["context"]["role_outputs"]["growth_analyst"]["profile"], "economy")
        self.assertEqual(pm_prompts[1]["context"]["role_outputs"]["value_skeptic"]["profile"], "economy")
        self.assertEqual(pm_prompts[1]["context"]["role_outputs"]["risk_manager"]["profile"], "deep")
        self.assertEqual(pm_prompts[1]["context"]["role_outputs"]["macro_strategist"]["profile"], "deep")
        self.assertEqual(
            set(result["roles"]["pm"].keys()),
            {
                "role",
                "round",
                "profile",
                "stance",
                "action",
                "confidence",
                "strong_objection",
                "summary",
                "valid",
                "invalid_reason",
            },
        )
        self.assertNotIn("prompt", result["roles"]["pm"])
        self.assertNotIn("raw", result["roles"]["pm"])
        self.assertEqual(result["roles"]["pm"]["invalid_reason"], "")

    def test_invalid_role_output_is_flagged_explicitly(self) -> None:
        def runner(role: str, profile: str, prompt: dict[str, object]) -> dict[str, object]:
            if role == "pm":
                return {"role": role, "profile": profile, "stance": "unknown", "summary": "pm summary", "confidence": 0.8}
            return {"role": role, "profile": profile, "stance": "watch", "summary": f"{role} summary", "confidence": 0.6}

        result = run_committee_analysis(_analysis(), run_role=runner)

        self.assertFalse(result["roles"]["pm"]["valid"])
        self.assertIn("invalid_stance", result["roles"]["pm"]["invalid_reason"])
        self.assertNotEqual(result["roles"]["pm"]["stance"], "unknown")

    def test_normalize_role_output_recovers_common_alias_fields_and_fenced_json(self) -> None:
        def runner(role: str, profile: str, prompt: dict[str, object]) -> object:
            if role == "growth_analyst":
                return {
                    "content": '```json\n{"recommendation":"buy","rationale":"growth thesis intact"}\n```',
                }
            if role == "value_skeptic":
                return {
                    "parsed": {
                        "action": "watch",
                        "thesis": "valuation no longer cheap",
                    }
                }
            if role == "risk_manager":
                return {
                    "output_text": '{"stance":"reduce","summary":"downside skew widening","objection":"true"}',
                }
            if role == "macro_strategist":
                return {
                    "data": {
                        "vote": "avoid",
                        "reasoning": "rates still a headwind",
                        "strong_objection": 1,
                    }
                }
            return {
                "message": {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"recommendation":"watch","conclusion":"mixed setup","confidence_score":"0.67"}',
                        }
                    ]
                }
            }

        result = run_committee_analysis(_analysis(), run_role=runner)

        self.assertTrue(result["roles"]["growth_analyst"]["valid"])
        self.assertEqual(result["roles"]["growth_analyst"]["stance"], "buy")
        self.assertEqual(result["roles"]["growth_analyst"]["summary"], "growth thesis intact")
        self.assertTrue(result["roles"]["risk_manager"]["valid"])
        self.assertTrue(result["roles"]["risk_manager"]["strong_objection"])
        self.assertEqual(result["roles"]["macro_strategist"]["stance"], "avoid")
        self.assertTrue(result["roles"]["macro_strategist"]["strong_objection"])
        self.assertTrue(result["roles"]["pm"]["valid"])
        self.assertEqual(result["roles"]["pm"]["summary"], "mixed setup")
        self.assertAlmostEqual(result["roles"]["pm"]["confidence"], 0.67)

    def test_default_runner_calls_openai_and_produces_valid_committee_payload(self) -> None:
        class _FakeResponse:
            def __init__(self, payload: dict[str, object]) -> None:
                import json

                self.output_text = json.dumps(payload)
                self.usage = SimpleNamespace(
                    input_tokens=100,
                    output_tokens=20,
                    total_tokens=120,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                )

        class _FakeResponsesApi:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []
                self._payloads = [
                    {"stance": "buy", "summary": "growth view"},
                    {"stance": "watch", "summary": "value view"},
                    {"stance": "watch", "summary": "risk view", "strong_objection": False},
                    {"stance": "watch", "summary": "macro view", "strong_objection": False},
                    {"stance": "buy", "summary": "pm view", "confidence": 0.82},
                ]

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return _FakeResponse(self._payloads.pop(0))

        class _FakeOpenAIClient:
            def __init__(self) -> None:
                self.responses = _FakeResponsesApi()

        fake_client = _FakeOpenAIClient()
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = lambda api_key=None: fake_client

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch("src.analyzer.committee.record_pipeline_event"),
        ):
            result = run_committee_analysis(_analysis())

        self.assertEqual(len(fake_client.responses.calls), 5)
        first_call = fake_client.responses.calls[0]
        self.assertEqual(first_call["model"], "gpt-5.4-mini")
        self.assertEqual(first_call["text"]["format"]["type"], "json_schema")
        self.assertTrue(result["roles"]["pm"]["valid"])
        self.assertEqual(result["roles"]["pm"]["summary"], "pm view")
        self.assertEqual(result["roles"]["pm"]["confidence"], 0.82)
        self.assertEqual(result["status"], "economy_only")


class CommitteeRetryAndSlimTests(unittest.TestCase):
    def test_default_runner_retries_on_rate_limit_then_succeeds(self) -> None:
        class _RateLimitError(Exception):
            status_code = 429

            def __init__(self) -> None:
                super().__init__("Error code: 429 - Rate limit reached (TPM)")

        _RateLimitError.__name__ = "RateLimitError"

        class _FakeResponse:
            def __init__(self, payload: dict[str, object]) -> None:
                import json

                self.output_text = json.dumps(payload)
                self.usage = SimpleNamespace(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                )

        payloads = [
            {"stance": "buy", "summary": "growth view"},
            {"stance": "watch", "summary": "value view"},
            {"stance": "watch", "summary": "risk view", "strong_objection": False},
            {"stance": "watch", "summary": "macro view", "strong_objection": False},
            {"stance": "buy", "summary": "pm view", "confidence": 0.82},
        ]

        class _FakeResponsesApi:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []
                self._fail_first_call = True

            def create(self, **kwargs):
                self.calls.append(kwargs)
                if self._fail_first_call and len(self.calls) == 1:
                    self._fail_first_call = False
                    raise _RateLimitError()
                return _FakeResponse(payloads.pop(0))

        class _FakeOpenAIClient:
            def __init__(self) -> None:
                self.responses = _FakeResponsesApi()

        fake_client = _FakeOpenAIClient()
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = lambda api_key=None: fake_client

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch("src.analyzer.committee.record_pipeline_event"),
            patch("src.analyzer.committee.time.sleep"),
        ):
            result = run_committee_analysis(_analysis())

        self.assertEqual(len(fake_client.responses.calls), 6)
        self.assertEqual(result["roles"]["growth_analyst"]["summary"], "growth view")
        self.assertTrue(result["roles"]["pm"]["valid"])

    def test_default_runner_falls_back_after_retry_budget_exhausted(self) -> None:
        class _RateLimitError(Exception):
            status_code = 429

            def __init__(self) -> None:
                super().__init__("Error code: 429 - TPM exceeded")

        _RateLimitError.__name__ = "RateLimitError"

        class _AlwaysFailsResponsesApi:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                raise _RateLimitError()

        class _FakeOpenAIClient:
            def __init__(self) -> None:
                self.responses = _AlwaysFailsResponsesApi()

        fake_client = _FakeOpenAIClient()
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = lambda api_key=None: fake_client

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch("src.analyzer.committee.record_pipeline_event"),
            patch("src.analyzer.committee.time.sleep"),
        ):
            result = run_committee_analysis(_analysis())

        from src.analyzer.committee import _RATE_LIMIT_MAX_ATTEMPTS

        self.assertGreaterEqual(len(fake_client.responses.calls), _RATE_LIMIT_MAX_ATTEMPTS * 5)
        for role in ("growth_analyst", "value_skeptic", "risk_manager", "macro_strategist", "pm"):
            payload = result["roles"][role]
            self.assertFalse(payload["valid"])
            self.assertIn("missing_summary", payload["invalid_reason"])

    def test_slim_payload_per_role_drops_historical_prices(self) -> None:
        from src.analyzer.committee_prompt import _slim_payload_for_role

        payload = {
            "ticker": "AAPL",
            "name": "Apple",
            "date": "2026-04-23",
            "summary": "s",
            "fundamentals": {"per": 34.6},
            "price_action": {"sma50": 260.27},
            "historical_prices": [{"date": "2026-04-22", "close": 270}] * 100,
        }
        for role in ("growth_analyst", "value_skeptic", "risk_manager", "macro_strategist", "pm"):
            slim = _slim_payload_for_role(payload, role)
            self.assertNotIn("historical_prices", slim)
            self.assertIn("ticker", slim)

    def test_slim_payload_whitelists_value_skeptic_to_valuation_fields(self) -> None:
        from src.analyzer.committee_prompt import _slim_payload_for_role

        payload = {
            "ticker": "AAPL",
            "name": "Apple",
            "date": "2026-04-23",
            "summary": "s",
            "fundamentals": {"per": 34.6},
            "valuation_score": 0.4,
            "price_action": {"sma50": 260.27},
            "options_summary": {"iv": 0.3},
            "historical_prices": [1, 2, 3],
        }
        slim = _slim_payload_for_role(payload, "value_skeptic")
        self.assertIn("fundamentals", slim)
        self.assertIn("valuation_score", slim)
        self.assertNotIn("price_action", slim)
        self.assertNotIn("options_summary", slim)

    def test_role_persona_and_stance_policy_appear_in_system_prompt(self) -> None:
        from src.analyzer.committee_prompt import build_value_skeptic_prompt

        prompt = build_value_skeptic_prompt(
            _analysis(),
            round_name="economy",
            profile_name="economy",
            max_summary_sentences=2,
            role_outputs={},
        )
        self.assertIn("가치 회의론자", prompt["system"])
        self.assertIn("Allowed stances for this role:", prompt["system"])
        self.assertNotIn("strong_buy", prompt["system"].split("Allowed stances for this role:", 1)[1].split(". ")[0])


if __name__ == "__main__":
    unittest.main()
