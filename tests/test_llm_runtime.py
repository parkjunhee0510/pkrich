from __future__ import annotations

import json
import os
import sys
import threading
import time
import types
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from src.analyzer.base import AnalysisContext, StructuredLLMModule
from src.analyzer.llm_runtime import _split_batches, parse_ticker_batch, run_structured_llm_module
from src.analyzer.prompts.base import PromptTemplate
from src.utils.model_config import ModelProfile


class _FakeStructuredModule(StructuredLLMModule):
    name = "fake_structured"
    requires = {"price"}
    produces = {"summary"}

    def analyze(self, ctx: AnalysisContext):
        raise NotImplementedError

    def build_batch_payload(self, ctx: AnalysisContext, batch_tickers: list[str]) -> list[dict[str, str]]:
        return [{"ticker": ticker} for ticker in batch_tickers]

    def build_system_prompt(self) -> str:
        return ""

    def build_user_prompt(self, batch_payload: list[dict[str, str]], ctx: AnalysisContext) -> str:
        return ""

    def response_schema(self) -> dict[str, object]:
        return {}

    def response_schema_name(self) -> str:
        return "fake_schema"

    def parse_batch_response(
        self,
        content: str,
        batch_tickers: list[str],
        ctx: AnalysisContext,
    ) -> dict[str, dict[str, str]]:
        return {
            entry["ticker"]: {"summary": entry["summary"]}
            for entry in parse_ticker_batch(content, batch_tickers)
        }

    def fallback_for_ticker(self, ticker: str, ctx: AnalysisContext) -> dict[str, str]:
        return {"summary": f"fallback:{ticker}"}


class _FakeResponse:
    def __init__(self, payload: dict[str, object], *, delay_seconds: float = 0.0) -> None:
        self.output_text = json.dumps(payload)
        self.usage = None
        self.delay_seconds = delay_seconds


class _FakeResponsesApi:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self._lock = threading.Lock()

    def create(self, **kwargs) -> _FakeResponse:
        with self._lock:
            self.calls.append(kwargs)
            if not self._responses:
                raise AssertionError("No fake responses remaining")
            response = self._responses.pop(0)
        if response.delay_seconds > 0:
            time.sleep(response.delay_seconds)
        return response


class _FakeOpenAIClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = _FakeResponsesApi(responses)


class ParseTickerBatchTests(unittest.TestCase):
    def test_allows_missing_tickers_for_partial_batch_repair(self) -> None:
        content = """
        {
          "tickers": [
            {"ticker": "AAPL", "summary": "ok"},
            {"ticker": "AMD", "summary": "ok"}
          ]
        }
        """
        parsed = parse_ticker_batch(content, ["AAPL", "AMD", "PL"])
        self.assertEqual(len(parsed), 2)
        self.assertEqual({entry["ticker"] for entry in parsed}, {"AAPL", "AMD"})

    def test_rejects_unexpected_ticker(self) -> None:
        content = """
        {
          "tickers": [
            {"ticker": "AAPL", "summary": "ok"},
            {"ticker": "MSFT", "summary": "bad"}
          ]
        }
        """
        with self.assertRaises(ValueError):
            parse_ticker_batch(content, ["AAPL", "AMD"])


class MissingTickerRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt_template = PromptTemplate(
            name="fake_structured",
            version="research_v1",
            system_template="system {module_name}",
            user_template="{batch_payload_json}",
            output_schema={
                "type": "object",
                "required": ["tickers"],
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["ticker", "summary"],
                            "properties": {
                                "ticker": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    }
                },
                "additionalProperties": False,
            },
        )
        self.model_profile = ModelProfile(
            name="economy",
            model="gpt-5.4-mini",
            prompt_version="research_v1",
            context_window=400000,
            max_output_tokens=32000,
            monthly_cost_estimate_usd=0.0,
            input_cost_per_1m_tokens=0.0,
            cached_input_cost_per_1m_tokens=0.0,
            output_cost_per_1m_tokens=0.0,
        )
        self.ctx = AnalysisContext(
            watchlist=[SimpleNamespace(ticker="AAPL"), SimpleNamespace(ticker="MSFT")],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            model_profile=self.model_profile,
            metadata={"llm_missing_retry_budget": 1, "llm_validation_retry_budget": 1},
            fallback_payload_by_ticker={
                "AAPL": {"summary": "fallback:AAPL"},
                "MSFT": {"summary": "fallback:MSFT"},
            },
            raw_payload_by_ticker={
                "AAPL": {"positioning": {"analyst_target_price": "120.00 USD"}},
                "MSFT": {},
            },
            intermediate_results={
                "AAPL": {},
                "MSFT": {},
            },
        )
        self.module = _FakeStructuredModule()

    def test_retries_missing_tickers_once_and_recovers_them(self) -> None:
        result = self._run_with_responses(
            [
                _FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}]}),
                _FakeResponse({"tickers": [{"ticker": "MSFT", "summary": "llm:MSFT"}]}),
            ]
        )

        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "llm:AAPL")
        self.assertEqual(result.results_by_ticker["MSFT"]["summary"], "llm:MSFT")
        self.assertEqual(result.diagnostics["missing_retry_batches"], 1)
        self.assertEqual(result.diagnostics["missing_retry_attempts"], 1)
        self.assertEqual(result.diagnostics["missing_retry_recovered_tickers"], 1)

    def test_uses_fallback_when_retry_still_misses_ticker(self) -> None:
        result = self._run_with_responses(
            [
                _FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}]}),
                _FakeResponse({"tickers": []}),
            ]
        )

        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "llm:AAPL")
        self.assertEqual(result.results_by_ticker["MSFT"]["summary"], "fallback:MSFT")
        self.assertEqual(result.diagnostics["missing_retry_batches"], 1)
        self.assertEqual(result.diagnostics["missing_retry_attempts"], 1)
        self.assertEqual(result.diagnostics["missing_retry_recovered_tickers"], 0)

    def test_signal_takeaway_module_uses_override_profile_model(self) -> None:
        fake_client = _FakeOpenAIClient(
            [_FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}, {"ticker": "MSFT", "summary": "llm:MSFT"}]})]
        )
        self.module.name = "signal_takeaway_module"
        result = self._run_with_responses([], client=fake_client)

        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "llm:AAPL")
        self.assertEqual(fake_client.responses.calls[0]["model"], "gpt-5.4")
        self.assertNotIn("temperature", fake_client.responses.calls[0])

    def test_non_reasoning_model_includes_temperature_when_configured(self) -> None:
        fake_client = _FakeOpenAIClient(
            [_FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}, {"ticker": "MSFT", "summary": "llm:MSFT"}]})]
        )
        self.ctx = AnalysisContext(
            watchlist=[SimpleNamespace(ticker="AAPL"), SimpleNamespace(ticker="MSFT")],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            model_profile=ModelProfile(
                name="custom",
                model="gpt-4.1-mini",
                prompt_version="research_v1",
                context_window=400000,
                max_output_tokens=32000,
                monthly_cost_estimate_usd=0.0,
                input_cost_per_1m_tokens=0.0,
                cached_input_cost_per_1m_tokens=0.0,
                output_cost_per_1m_tokens=0.0,
                temperature=0.2,
            ),
            metadata={"llm_missing_retry_budget": 1},
            fallback_payload_by_ticker={
                "AAPL": {"summary": "fallback:AAPL"},
                "MSFT": {"summary": "fallback:MSFT"},
            },
            intermediate_results={"AAPL": {}, "MSFT": {}},
        )

        self._run_with_responses([], client=fake_client)

        self.assertEqual(fake_client.responses.calls[0]["temperature"], 0.2)

    def test_sends_prompt_cache_key_for_cache_routing(self) -> None:
        fake_client = _FakeOpenAIClient(
            [_FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}, {"ticker": "MSFT", "summary": "llm:MSFT"}]})]
        )
        self._run_with_responses([], client=fake_client)

        self.assertEqual(
            fake_client.responses.calls[0]["prompt_cache_key"],
            "research_v1:fake_structured",
        )

    def test_evidence_hash_failure_does_not_skip_provider_call(self) -> None:
        fake_client = _FakeOpenAIClient(
            [_FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}, {"ticker": "MSFT", "summary": "llm:MSFT"}]})]
        )

        with patch("src.analyzer.llm_runtime.evidence_hash", side_effect=RuntimeError("hash boom")):
            result = self._run_with_responses([], client=fake_client)

        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "llm:AAPL")
        self.assertEqual(len(fake_client.responses.calls), 1)

    def test_records_evidence_manifest_for_structured_batch(self) -> None:
        fake_client = _FakeOpenAIClient(
            [_FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "llm:AAPL"}, {"ticker": "MSFT", "summary": "llm:MSFT"}]})]
        )
        self.ctx = AnalysisContext(
            watchlist=[SimpleNamespace(ticker="AAPL"), SimpleNamespace(ticker="MSFT")],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            macro_context={"vix": {"level": "18"}, "market_regime": {"regime": "neutral"}},
            model_profile=ModelProfile(
                name="economy",
                model="gpt-5.4-mini",
                prompt_version="research_v1",
                context_window=400000,
                max_output_tokens=32000,
                monthly_cost_estimate_usd=0.0,
                input_cost_per_1m_tokens=0.0,
                cached_input_cost_per_1m_tokens=0.0,
                output_cost_per_1m_tokens=0.0,
            ),
            metadata={"execution_mode": "full"},
            raw_payload_by_ticker={"AAPL": {"price": 100}, "MSFT": {"price": 200}},
            fallback_payload_by_ticker={"AAPL": {"summary": "fallback:AAPL"}, "MSFT": {"summary": "fallback:MSFT"}},
            intermediate_results={"AAPL": {"trade_frame": {"entry": "100"}}, "MSFT": {"trade_frame": {"entry": "200"}}},
        )

        with patch("src.analyzer.llm_runtime.write_evidence_record") as writer:
            result = self._run_with_responses([], client=fake_client, patch_evidence_writer=False)

        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "llm:AAPL")
        self.assertEqual(writer.call_count, 2)
        first_record = writer.call_args_list[0].args[0]
        self.assertEqual(first_record["scope"], "ticker")
        self.assertEqual(first_record["stage"], "analyzer")
        self.assertEqual(first_record["module"], "fake_structured")
        self.assertEqual(first_record["ticker"], "AAPL")
        self.assertEqual(first_record["batch_tickers"], ["AAPL", "MSFT"])
        self.assertEqual(first_record["execution_mode"], "full")
        self.assertEqual(first_record["model_profile"], "economy")
        self.assertEqual(first_record["prompt_version"], "research_v1")
        self.assertTrue(first_record["raw_payload_present"])
        self.assertTrue(first_record["fallback_payload_present"])
        self.assertTrue(first_record["macro_context_present"])
        self.assertTrue(first_record["market_regime_present"])
        self.assertTrue(first_record["upstream_payload_present"])
        self.assertTrue(first_record["raw_payload_hash"].startswith("sha256:"))
        self.assertTrue(first_record["fallback_payload_hash"].startswith("sha256:"))
        self.assertTrue(first_record["upstream_payload_hash"].startswith("sha256:"))
        self.assertTrue(first_record["macro_context_hash"].startswith("sha256:"))
        self.assertTrue(first_record["market_regime_hash"].startswith("sha256:"))
        self.assertTrue(first_record["prompt_template_hash"].startswith("sha256:"))

    def test_retries_single_ticker_after_fact_warning_and_recovers(self) -> None:
        fake_client = _FakeOpenAIClient(
            [
                _FakeResponse(
                    {
                        "tickers": [
                            {"ticker": "AAPL", "summary": "목표 가격은 999.00 USD로 봅니다."},
                            {"ticker": "MSFT", "summary": "정상 요약"},
                        ]
                    }
                ),
                _FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "목표 가격은 120.00 USD로 봅니다."}]}),
            ]
        )

        result = self._run_with_responses([], client=fake_client)

        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "목표 가격은 120.00 USD로 봅니다.")
        self.assertEqual(result.results_by_ticker["MSFT"]["summary"], "정상 요약")
        self.assertEqual(result.diagnostics["validation_retry_batches"], 1)
        self.assertEqual(result.diagnostics["validation_retry_attempts"], 1)
        self.assertEqual(result.diagnostics["validation_retry_recovered_tickers"], 1)
        self.assertEqual(len(fake_client.responses.calls), 2)
        self.assertIn("VALIDATION RETRY RULES", fake_client.responses.calls[1]["input"][1]["content"][0]["text"])
        self.assertEqual(fake_client.responses.calls[1]["prompt_cache_key"], "research_v1:fake_structured:validation-retry")

    def test_validation_retry_uses_lower_temperature_for_non_reasoning_model(self) -> None:
        self.ctx = AnalysisContext(
            watchlist=[SimpleNamespace(ticker="AAPL"), SimpleNamespace(ticker="MSFT")],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            model_profile=ModelProfile(
                name="custom",
                model="gpt-4.1-mini",
                prompt_version="research_v1",
                context_window=400000,
                max_output_tokens=32000,
                monthly_cost_estimate_usd=0.0,
                input_cost_per_1m_tokens=0.0,
                cached_input_cost_per_1m_tokens=0.0,
                output_cost_per_1m_tokens=0.0,
                temperature=0.2,
            ),
            metadata={"llm_missing_retry_budget": 1, "llm_validation_retry_budget": 1},
            fallback_payload_by_ticker={
                "AAPL": {"summary": "fallback:AAPL"},
                "MSFT": {"summary": "fallback:MSFT"},
            },
            raw_payload_by_ticker={
                "AAPL": {"positioning": {"analyst_target_price": "120.00 USD"}},
                "MSFT": {},
            },
            intermediate_results={"AAPL": {}, "MSFT": {}},
        )
        fake_client = _FakeOpenAIClient(
            [
                _FakeResponse(
                    {
                        "tickers": [
                            {"ticker": "AAPL", "summary": "목표 가격은 999.00 USD로 봅니다."},
                            {"ticker": "MSFT", "summary": "정상 요약"},
                        ]
                    }
                ),
                _FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "목표 가격은 120.00 USD로 봅니다."}]}),
            ]
        )

        self._run_with_responses([], client=fake_client)

        self.assertEqual(fake_client.responses.calls[0]["temperature"], 0.2)
        self.assertEqual(fake_client.responses.calls[1]["temperature"], 0.1)

    def _run_with_responses(
        self,
        responses: list[_FakeResponse],
        client: _FakeOpenAIClient | None = None,
        *,
        patch_evidence_writer: bool = True,
    ):
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = lambda api_key=None: client or _FakeOpenAIClient(responses)
        patches = [
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch("src.analyzer.llm_runtime.record_pipeline_event"),
        ]
        if patch_evidence_writer:
            patches.append(patch("src.analyzer.llm_runtime.write_evidence_record"))
        with patches[0], patches[1], patches[2]:
            if patch_evidence_writer:
                with patches[3]:
                    return run_structured_llm_module(
                        self.module,
                        self.ctx,
                        prompt_template_override=self.prompt_template,
                    )
            return run_structured_llm_module(
                self.module,
                self.ctx,
                prompt_template_override=self.prompt_template,
            )


class SplitBatchesModuleBatchCapTests(unittest.TestCase):
    def test_signal_takeaway_batches_are_capped_at_three(self) -> None:
        module = _FakeStructuredModule()
        module.name = "signal_takeaway_module"
        model_profile = ModelProfile(
            name="economy",
            model="gpt-5.4-mini",
            prompt_version="research_v1",
            context_window=400000,
            max_output_tokens=32000,
            monthly_cost_estimate_usd=0.0,
            input_cost_per_1m_tokens=0.0,
            cached_input_cost_per_1m_tokens=0.0,
            output_cost_per_1m_tokens=0.0,
        )
        ctx = AnalysisContext(
            watchlist=[],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            model_profile=model_profile,
        )

        tickers = ["AAPL", "MSFT", "AMD", "CAT", "XOM", "T", "KO"]
        batches = _split_batches(module, ctx, tickers)

        self.assertTrue(all(len(batch) <= 3 for batch in batches))
        self.assertEqual(sum(len(batch) for batch in batches), len(tickers))
        self.assertEqual([batch[0] for batch in batches], ["AAPL", "CAT", "KO"])
        self.assertEqual([len(batch) for batch in batches], [3, 3, 1])

    def test_module_without_override_is_unbounded(self) -> None:
        module = _FakeStructuredModule()
        module.name = "news_analysis_module"
        model_profile = ModelProfile(
            name="economy",
            model="gpt-5.4-mini",
            prompt_version="research_v1",
            context_window=400000,
            max_output_tokens=32000,
            monthly_cost_estimate_usd=0.0,
            input_cost_per_1m_tokens=0.0,
            cached_input_cost_per_1m_tokens=0.0,
            output_cost_per_1m_tokens=0.0,
        )
        ctx = AnalysisContext(
            watchlist=[],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            model_profile=model_profile,
        )

        tickers = ["AAPL", "MSFT", "AMD", "CAT", "XOM", "T", "KO"]
        batches = _split_batches(module, ctx, tickers)

        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 7)


class ParallelBatchExecutionTests(unittest.TestCase):
    def test_processes_multiple_batches_in_parallel(self) -> None:
        module = _FakeStructuredModule()
        module.name = "signal_takeaway_module"
        ctx = AnalysisContext(
            watchlist=[SimpleNamespace(ticker=ticker) for ticker in ["AAPL", "MSFT", "AMD", "CAT", "XOM", "T", "KO"]],
            collected={},
            news_map={},
            run_date=date(2026, 4, 21),
            model_profile=ModelProfile(
                name="economy",
                model="gpt-5.4-mini",
                prompt_version="research_v1",
                context_window=400000,
                max_output_tokens=32000,
                monthly_cost_estimate_usd=0.0,
                input_cost_per_1m_tokens=0.0,
                cached_input_cost_per_1m_tokens=0.0,
                output_cost_per_1m_tokens=0.0,
            ),
            metadata={
                "llm_missing_retry_budget": 0,
                "llm_validation_retry_budget": 0,
                "llm_batch_max_workers": 3,
            },
            fallback_payload_by_ticker={ticker: {"summary": f"fallback:{ticker}"} for ticker in ["AAPL", "MSFT", "AMD", "CAT", "XOM", "T", "KO"]},
            intermediate_results={ticker: {} for ticker in ["AAPL", "MSFT", "AMD", "CAT", "XOM", "T", "KO"]},
        )
        prompt_template = PromptTemplate(
            name="signal_takeaway_module",
            version="research_v1",
            system_template="system {module_name}",
            user_template="{batch_payload_json}",
            output_schema={
                "type": "object",
                "required": ["tickers"],
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["ticker", "summary"],
                            "properties": {
                                "ticker": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    }
                },
                "additionalProperties": False,
            },
        )
        fake_client = _FakeOpenAIClient(
            [
                _FakeResponse({"tickers": [{"ticker": "AAPL", "summary": "AAPL"}, {"ticker": "MSFT", "summary": "MSFT"}, {"ticker": "AMD", "summary": "AMD"}]}, delay_seconds=0.1),
                _FakeResponse({"tickers": [{"ticker": "CAT", "summary": "CAT"}, {"ticker": "XOM", "summary": "XOM"}, {"ticker": "T", "summary": "T"}]}, delay_seconds=0.1),
                _FakeResponse({"tickers": [{"ticker": "KO", "summary": "KO"}]}, delay_seconds=0.1),
            ]
        )

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = lambda api_key=None: fake_client
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False),
            patch.dict(sys.modules, {"openai": fake_openai}),
            patch("src.analyzer.llm_runtime.record_pipeline_event"),
            patch("src.analyzer.llm_runtime.write_evidence_record"),
        ):
            start = time.monotonic()
            result = run_structured_llm_module(
                module,
                ctx,
                prompt_template_override=prompt_template,
            )
            elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.25)
        self.assertEqual(result.diagnostics["batch_count"], 3)
        self.assertEqual(result.diagnostics["parallel_batch_workers"], 3)
        self.assertEqual(result.results_by_ticker["KO"]["summary"], "KO")
        self.assertEqual(len(fake_client.responses.calls), 3)


if __name__ == "__main__":
    unittest.main()
