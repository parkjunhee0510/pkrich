from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from src.eval.replay import (
    LLMReplayClient,
    OpenAIReplayClient,
    ReplayConfig,
    run_replay,
    estimate_cost,
)
from src.analyzer.base import ModuleResult


class FakeClient(LLMReplayClient):
    def __init__(self, responses: list[str], cost_per_call: float = 0.05) -> None:
        self.responses = list(responses)
        self.cost_per_call = cost_per_call
        self.calls = 0

    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        self.calls += 1
        return {"summary": self.responses[(self.calls - 1) % len(self.responses)],
                "cost_usd": self.cost_per_call}


class TestReplay(unittest.TestCase):
    def test_dry_run_makes_no_calls(self):
        client = FakeClient(responses=["x"])
        cfg = ReplayConfig(tickers=("AAPL", "MSFT"), runs_per_ticker=3,
                           max_cost_usd=1.0, dry_run=True)
        result = run_replay(client=client, config=cfg)
        self.assertEqual(client.calls, 0)
        self.assertGreater(result.estimated_cost_usd, 0.0)

    def test_cost_cap_aborts(self):
        client = FakeClient(responses=["x"], cost_per_call=0.40)
        cfg = ReplayConfig(tickers=("AAPL", "MSFT"), runs_per_ticker=3,
                           max_cost_usd=1.0, dry_run=False)
        result = run_replay(client=client, config=cfg)
        self.assertTrue(result.aborted)
        self.assertLessEqual(client.calls, 3)

    def test_full_run_records_per_ticker_outputs(self):
        client = FakeClient(responses=["a", "a", "a"], cost_per_call=0.05)
        cfg = ReplayConfig(tickers=("AAPL",), runs_per_ticker=3,
                           max_cost_usd=1.0, dry_run=False)
        result = run_replay(client=client, config=cfg)
        self.assertFalse(result.aborted)
        self.assertEqual(len(result.outputs["AAPL"]), 3)
        self.assertAlmostEqual(result.actual_cost_usd, 0.15, places=3)

    def test_estimate_cost(self):
        cost = estimate_cost(tickers=("AAPL", "MSFT"), runs_per_ticker=3,
                             cost_per_call_usd=0.05)
        self.assertAlmostEqual(cost, 0.30, places=3)

    def test_openai_client_uses_structured_runtime_contract(self):
        client = OpenAIReplayClient(model_profile="economy")
        with mock.patch(
            "src.analyzer.llm_runtime.run_structured_llm_module",
            return_value=ModuleResult(
                results_by_ticker={
                    "AAPL": {"signal_or_takeaway": "buy signal with stable summary text"}
                }
            ),
        ) as fake_run:
            result = client.call("AAPL", 0)

        self.assertEqual(result["action"], "buy")
        self.assertEqual(result["summary"], "buy signal with stable summary text")
        args, kwargs = fake_run.call_args
        self.assertEqual(len(args), 2)
        self.assertFalse({"module_name", "ticker", "model_profile"} & set(kwargs))


if __name__ == "__main__":
    unittest.main()
