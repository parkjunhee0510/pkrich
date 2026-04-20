from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult, StructuredLLMModule
from src.analyzer.orchestrator import AnalysisOrchestrator
from src.analyzer.registry import ModuleRegistry
from src.types import CollectedTickerData, PortfolioPosition, PortfolioSummary, WatchlistItem
from src.utils.model_config import load_model_profile


def _make_collected() -> CollectedTickerData:
    return CollectedTickerData(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        price=210.0,
        change_percent=1.2,
        currency="USD",
        market_cap="3T",
        pe_ratio="28",
        eps="6.5",
        summary_note="",
        upcoming_events=[{"type": "earnings", "date": "2026-04-30", "days_until": "14"}],
        quarterly_financials=[{"quarter": "2025-Q4", "surprise_pct": "+5.0%", "beat_miss": "beat"}],
    )


class _NonLLMModule(AnalysisModule):
    name = "non_llm"
    requires = {"price"}
    produces = {"valuation_score"}
    priority = 10
    llm_required = False

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        return ModuleResult(results_by_ticker={"AAPL": {"valuation_score": {"score": "8/10"}}})


class _DependentModule(AnalysisModule):
    name = "dependent"
    requires = {"valuation_score"}
    produces = {"summary"}
    priority = 20
    llm_required = False

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        return ModuleResult(results_by_ticker={"AAPL": {"summary": "모듈 테스트 요약입니다."}})


class _PortfolioModule(AnalysisModule):
    name = "portfolio_risk_module"
    requires = {"portfolio_summary"}
    produces = {"portfolio_risk"}
    priority = 5
    llm_required = False

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        return ModuleResult(portfolio_result={"portfolio_risk": {"risk_grade": "B", "hhi": 1200.0}})


class _LLMModule(StructuredLLMModule):
    name = "signal_takeaway_module"
    requires = {"price"}
    produces = {"signal_or_takeaway"}
    priority = 30

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        raise NotImplementedError

    def build_batch_payload(self, ctx: AnalysisContext, batch_tickers: list[str]):
        return [{"ticker": ticker} for ticker in batch_tickers]

    def build_system_prompt(self) -> str:
        return ""

    def build_user_prompt(self, batch_payload, ctx: AnalysisContext) -> str:
        return ""

    def response_schema(self) -> dict[str, object]:
        return {"type": "object"}

    def response_schema_name(self) -> str:
        return "signal_takeaway_batch"

    def parse_batch_response(self, content: str, batch_tickers: list[str], ctx: AnalysisContext):
        return {ticker: {"signal_or_takeaway": "중립 관찰 — 테스트"} for ticker in batch_tickers}

    def fallback_for_ticker(self, ticker: str, ctx: AnalysisContext):
        return {"signal_or_takeaway": "중립 관찰 — 테스트"}


class AnalysisOrchestratorTests(unittest.TestCase):
    def test_orchestrator_merges_module_results_into_ticker_analysis(self) -> None:
        registry = ModuleRegistry()
        registry.register(_NonLLMModule())
        registry.register(_DependentModule())
        orchestrator = AnalysisOrchestrator(registry)
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "", "FMP_API_KEY": ""}, clear=False):
            analyses = orchestrator.analyze_all(
                [WatchlistItem(ticker="AAPL", name="Apple Inc.")],
                {"AAPL": _make_collected()},
                {},
                date(2026, 4, 16),
            )
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0].valuation_score["score"], "8/10")
        self.assertEqual(analyses[0].summary, "모듈 테스트 요약입니다.")
        self.assertEqual(orchestrator.diagnostics["executed_modules"], ["non_llm", "dependent"])

    def test_orchestrator_passes_model_profile_prompt_version_into_llm_runtime(self) -> None:
        registry = ModuleRegistry()
        registry.register(_LLMModule())
        model_profile = load_model_profile(profile_name="deep")
        orchestrator = AnalysisOrchestrator(registry, model_profile=model_profile)

        captured: dict[str, str] = {}

        def _fake_run(module: StructuredLLMModule, ctx: AnalysisContext) -> ModuleResult:
            captured["prompt_version"] = ctx.model_profile.prompt_version
            return ModuleResult(results_by_ticker={"AAPL": {"signal_or_takeaway": "중립 관찰 — 테스트"}})

        with patch("src.analyzer.orchestrator.run_structured_llm_module", side_effect=_fake_run):
            analyses = orchestrator.analyze_all(
                [WatchlistItem(ticker="AAPL", name="Apple Inc.")],
                {"AAPL": _make_collected()},
                {},
                date(2026, 4, 16),
            )

        self.assertEqual(captured["prompt_version"], "research_v2")
        self.assertEqual(analyses[0].signal_or_takeaway, "중립 관찰 — 테스트")

    def test_orchestrator_collects_portfolio_result_from_module(self) -> None:
        registry = ModuleRegistry()
        registry.register(_PortfolioModule())
        orchestrator = AnalysisOrchestrator(registry)

        orchestrator.analyze_all(
            [WatchlistItem(ticker="AAPL", name="Apple Inc.")],
            {"AAPL": _make_collected()},
            {},
            date(2026, 4, 16),
            portfolio_summary=PortfolioSummary(
                positions=[PortfolioPosition("AAPL", 10, 100.0, "USD", 210.0, 2100.0, 1000.0, 1100.0, 110.0)],
                total_market_value=2100.0,
                total_cost_basis=1000.0,
                total_unrealized_pnl=1100.0,
                total_unrealized_return_pct=110.0,
            ),
        )

        self.assertEqual(orchestrator.portfolio_result["portfolio_risk"]["risk_grade"], "B")

    def test_orchestrator_llm_only_reuses_existing_intermediate_results(self) -> None:
        registry = ModuleRegistry()
        registry.register(_NonLLMModule())
        registry.register(_LLMModule())
        orchestrator = AnalysisOrchestrator(registry, model_profile=load_model_profile(profile_name="deep"))

        captured: dict[str, object] = {}

        def _fake_run(module: StructuredLLMModule, ctx: AnalysisContext) -> ModuleResult:
            captured["valuation_score"] = ctx.intermediate_results["AAPL"]["valuation_score"]
            return ModuleResult(results_by_ticker={"AAPL": {"signal_or_takeaway": "deep 재검토"}})

        with patch("src.analyzer.orchestrator.run_structured_llm_module", side_effect=_fake_run):
            analyses = orchestrator.analyze_all(
                [WatchlistItem(ticker="AAPL", name="Apple Inc.")],
                {"AAPL": _make_collected()},
                {},
                date(2026, 4, 16),
                execution_mode="llm_only",
                initial_intermediate_results={
                    "AAPL": {
                        "ticker": "AAPL",
                        "name": "Apple Inc.",
                        "date": "2026-04-16",
                        "summary": "기존 요약",
                        "key_news": [],
                        "news_references": [],
                        "financial_highlights": [],
                        "risks_or_watchpoints": [],
                        "signal_or_takeaway": "기존",
                        "data_snapshot": {},
                        "fundamentals": {},
                        "price_action": {},
                        "quarterly_financials": [],
                        "upcoming_events": [],
                        "news_tone": {},
                        "trade_frame": {},
                        "options_summary": {},
                        "signal_history": [],
                        "sector_comparison": {},
                        "peer_rank": {},
                        "valuation_score": {"score": "8/10"},
                        "analysis_consensus": {},
                        "historical_prices": [],
                    }
                },
            )

        self.assertEqual(captured["valuation_score"], {"score": "8/10"})
        self.assertEqual(orchestrator.diagnostics["execution_mode"], "llm_only")
        self.assertEqual(orchestrator.diagnostics["executed_modules"], ["signal_takeaway_module"])
        self.assertEqual(analyses[0].signal_or_takeaway, "deep 재검토")


if __name__ == "__main__":
    unittest.main()
