from __future__ import annotations

import unittest
from datetime import date
from typing import Any

from src.eval.checks.d1_semantic_drift import D1SemanticDrift
from src.eval.replay import LLMReplayClient
from tests.eval.fixtures.builders import make_dataset


class _DeterministicClient(LLMReplayClient):
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        return {"action": "buy", "summary": "Strong fundamentals.", "cost_usd": 0.05}


class _DriftyClient(LLMReplayClient):
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        actions = ["buy", "watch", "avoid"]
        summaries = ["Strong.", "Mixed signals today.", "Bearish technical."]
        return {"action": actions[run_index % 3],
                "summary": summaries[run_index % 3], "cost_usd": 0.05}


class TestD1(unittest.TestCase):
    def test_pass_when_deterministic(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        check = D1SemanticDrift(client=_DeterministicClient(),
                                replay_tickers=("AAPL",), runs_per_ticker=3,
                                max_cost_usd=1.0, dry_run=False)
        result = check.run(ds)
        self.assertEqual(result.severity, "pass")

    def test_fail_when_drifty(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        check = D1SemanticDrift(client=_DriftyClient(),
                                replay_tickers=("AAPL",), runs_per_ticker=3,
                                max_cost_usd=1.0, dry_run=False)
        result = check.run(ds)
        self.assertEqual(result.severity, "fail")

    def test_dry_run_returns_info(self):
        ds = make_dataset(tickers=("AAPL",), end=date(2026, 4, 28))
        check = D1SemanticDrift(client=_DeterministicClient(),
                                replay_tickers=("AAPL",), runs_per_ticker=3,
                                max_cost_usd=1.0, dry_run=True)
        result = check.run(ds)
        self.assertEqual(result.severity, "info")
        self.assertIn("estimated_cost_usd", result.metrics)


if __name__ == "__main__":
    unittest.main()
