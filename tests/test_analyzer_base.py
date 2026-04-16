from __future__ import annotations

import unittest
from datetime import date

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult, sort_modules
from src.types import WatchlistItem


class _StubModule(AnalysisModule):
    def __init__(self, name: str, priority: int, requires: set[str] | None = None) -> None:
        self.name = name
        self.priority = priority
        self.requires = requires or set()
        self.produces = {f"{name}_field"}

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        tickers = [item.ticker for item in ctx.watchlist]
        return ModuleResult(results_by_ticker={ticker: {self.name: self.priority} for ticker in tickers})


class TestAnalyzerBase(unittest.TestCase):
    def test_sort_modules_uses_priority_then_name(self) -> None:
        modules = [
            _StubModule("beta", 20),
            _StubModule("alpha", 10),
            _StubModule("gamma", 10),
        ]
        ordered = sort_modules(modules)
        self.assertEqual([module.name for module in ordered], ["alpha", "gamma", "beta"])

    def test_context_tracks_available_inputs(self) -> None:
        ctx = AnalysisContext(
            watchlist=[WatchlistItem(ticker="AAPL", name="Apple")],
            collected={},
            news_map={},
            run_date=date(2026, 4, 16),
            available_inputs={"price", "news"},
        )
        self.assertIn("price", ctx.available_inputs)
        self.assertEqual(ctx.watchlist[0].ticker, "AAPL")
