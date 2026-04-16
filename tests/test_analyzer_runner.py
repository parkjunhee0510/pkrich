from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult
from src.analyzer.runner import run_analysis_modules
from src.types import WatchlistItem


class _RunnerModule(AnalysisModule):
    def __init__(
        self,
        name: str,
        priority: int,
        payload: dict[str, dict[str, object]],
        *,
        requires: set[str] | None = None,
        produces: set[str] | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self.requires = requires or set()
        self.produces = produces or {name}
        self._payload = payload

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        return ModuleResult(results_by_ticker=self._payload, diagnostics={"ran": True})


class TestAnalyzerRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = AnalysisContext(
            watchlist=[WatchlistItem(ticker="AAPL", name="Apple")],
            collected={},
            news_map={},
            run_date=date(2026, 4, 16),
            available_inputs={"price", "news"},
        )

    def test_runner_merges_results_and_overwrites_later_keys(self) -> None:
        modules = [
            _RunnerModule("first", 10, {"AAPL": {"summary": "one", "score": 1}}, produces={"summary"}),
            _RunnerModule("second", 20, {"AAPL": {"summary": "two", "signal": "watch"}}, requires={"summary"}),
        ]
        result = run_analysis_modules(self.ctx, modules)
        self.assertEqual(result.results_by_ticker["AAPL"]["summary"], "two")
        self.assertEqual(result.results_by_ticker["AAPL"]["score"], 1)
        self.assertEqual(result.results_by_ticker["AAPL"]["signal"], "watch")

    def test_runner_skips_missing_requires(self) -> None:
        modules = [
            _RunnerModule("missing", 10, {"AAPL": {"summary": "one"}}, requires={"fundamentals"}),
        ]
        result = run_analysis_modules(self.ctx, modules)
        self.assertEqual(result.results_by_ticker, {})
        self.assertEqual(result.diagnostics["skipped_modules"][0]["module"], "missing")
