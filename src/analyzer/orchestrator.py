from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from src.analyzer.base import AnalysisContext, AnalysisModule, StructuredLLMModule
from src.analyzer.llm_runtime import run_structured_llm_module
from src.analyzer.payloads import analyses_from_payloads, build_fallback_payloads, build_raw_payloads
from src.analyzer.quality_summary import build_quality_summary, merge_quality_summary_maps
from src.analyzer.registry import ModuleRegistry
from src.types import CollectedTickerData, NewsItem, PortfolioSummary, TickerAnalysis, WatchlistItem
from src.utils.model_config import ModelProfile, load_model_profile


class AnalysisOrchestrator:
    def __init__(
        self,
        registry: ModuleRegistry,
        model_profile: ModelProfile | None = None,
        logger: Any | None = None,
    ) -> None:
        self.registry = registry
        self.model_profile = model_profile
        self.logger = logger
        self.diagnostics: dict[str, Any] = {}
        self.portfolio_result: dict[str, Any] = {}
        self.quality_summary_by_ticker: dict[str, dict[str, Any]] = {}

    def analyze_all(
        self,
        watchlist: list[WatchlistItem],
        collected: dict[str, CollectedTickerData],
        news_map: dict[str, list[NewsItem]],
        run_date: date,
        *,
        macro_context: dict[str, Any] | None = None,
        signal_history_map: dict[str, list[dict[str, str]]] | None = None,
        portfolio_account_size: float | None = None,
        portfolio_summary: PortfolioSummary | None = None,
        peer_candidates_by_ticker: dict[str, list[dict[str, Any]]] | None = None,
        execution_mode: str = "full",
        raw_payload_by_ticker: dict[str, dict[str, Any]] | None = None,
        fallback_payload_by_ticker: dict[str, dict[str, Any]] | None = None,
        initial_intermediate_results: dict[str, dict[str, Any]] | None = None,
    ) -> list[TickerAnalysis]:
        raw_payload_by_ticker = raw_payload_by_ticker or build_raw_payloads(
            watchlist,
            collected,
            news_map,
            signal_history_map=signal_history_map,
            peer_candidates_by_ticker=peer_candidates_by_ticker,
        )
        fallback_payload_by_ticker = fallback_payload_by_ticker or build_fallback_payloads(
            watchlist,
            collected,
            news_map,
            run_date,
            raw_payload_by_ticker=raw_payload_by_ticker,
            signal_history_map=signal_history_map,
            account_size_hint=portfolio_account_size,
        )
        merged = {
            ticker: dict(payload)
            for ticker, payload in (initial_intermediate_results or fallback_payload_by_ticker).items()
        }
        derived_inputs = (
            {
                key
                for payload in merged.values()
                for key in payload.keys()
            }
            if execution_mode == "llm_only"
            else set()
        )
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map=news_map,
            run_date=run_date,
            portfolio_summary=portfolio_summary,
            macro_context=macro_context,
            signal_history_map=signal_history_map,
            portfolio_account_size=portfolio_account_size,
            model_profile=self.model_profile or load_model_profile(),
            logger=self.logger,
            metadata={"execution_mode": execution_mode},
            available_inputs={
                "price",
                "fundamentals",
                "news",
                "upcoming_events",
                "quarterly_financials",
                "options_summary",
                "historical_prices",
                "portfolio_summary",
                "peer_candidates",
            } | derived_inputs,
            raw_payload_by_ticker=raw_payload_by_ticker,
            fallback_payload_by_ticker=fallback_payload_by_ticker,
            intermediate_results=merged,
        )
        ordered_modules = self.registry.resolve_order(set(ctx.available_inputs))
        if execution_mode == "llm_only":
            modules_to_run = [module for module in ordered_modules if module.llm_required]
        else:
            non_llm_modules = [module for module in ordered_modules if not module.llm_required]
            llm_modules = [module for module in ordered_modules if module.llm_required]
            modules_to_run = [*non_llm_modules, *llm_modules]
        diagnostics: dict[str, Any] = {
            "execution_mode": execution_mode,
            "executed_modules": [],
            "module_diagnostics": {},
        }
        portfolio_result: dict[str, Any] = {}
        quality_summary_by_ticker: dict[str, dict[str, Any]] = {}

        for module in modules_to_run:
            module_ctx = replace(ctx, intermediate_results=merged)
            result = self._run_module(module, module_ctx)
            diagnostics["executed_modules"].append(module.name)
            diagnostics["module_diagnostics"][module.name] = result.diagnostics
            quality_summary_by_ticker = merge_quality_summary_maps(
                quality_summary_by_ticker,
                build_quality_summary(
                    result.diagnostics,
                    tickers=list(result.results_by_ticker.keys()),
                ),
            )
            for ticker, payload in result.results_by_ticker.items():
                merged.setdefault(ticker, {}).update(payload)
            if result.portfolio_result:
                portfolio_result.update(result.portfolio_result)

        self.diagnostics = diagnostics
        self.portfolio_result = portfolio_result
        self.quality_summary_by_ticker = quality_summary_by_ticker
        return analyses_from_payloads(watchlist, merged)

    def _run_module(self, module: AnalysisModule, ctx: AnalysisContext):
        if isinstance(module, StructuredLLMModule):
            return run_structured_llm_module(module, ctx, capture_validation_details=True)
        return module.analyze(ctx)
