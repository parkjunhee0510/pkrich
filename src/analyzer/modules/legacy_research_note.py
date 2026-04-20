from __future__ import annotations

from typing import Any

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult


class LegacyResearchNoteModule(AnalysisModule):
    name = "legacy_research_note"
    requires = {"price", "fundamentals", "news", "upcoming_events", "quarterly_financials"}
    produces = {
        "summary",
        "key_news",
        "financial_highlights",
        "risks_or_watchpoints",
        "signal_or_takeaway",
        "data_snapshot",
        "fundamentals",
        "price_action",
        "quarterly_financials",
        "upcoming_events",
        "news_tone",
        "trade_frame",
        "options_summary",
        "signal_history",
        "sector_comparison",
        "valuation_score",
        "historical_prices",
    }
    priority = 100
    llm_required = True

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        from src.analyzer import research_note

        analyses = research_note._run_legacy_analysis_pipeline(
            ctx.watchlist,
            ctx.collected,
            ctx.news_map,
            ctx.run_date,
            macro_context=ctx.macro_context,
            signal_history_map=ctx.signal_history_map,
            model_profile_name=ctx.model_profile.name if ctx.model_profile else None,
            portfolio_account_size=ctx.portfolio_account_size,
            model_profile=ctx.model_profile,
        )
        return ModuleResult(
            results_by_ticker={
                analysis.ticker: research_note._analysis_to_payload(analysis)
                for analysis in analyses
            },
            diagnostics={"ticker_count": len(analyses)},
        )

    def estimate_tokens(self, ctx: AnalysisContext) -> int:
        from src.analyzer import research_note

        model_profile = ctx.model_profile
        if model_profile is None:
            return 0
        return research_note._estimate_watchlist_tokens(
            ctx.watchlist,
            ctx.collected,
            ctx.news_map,
            ctx.run_date,
            model_profile=model_profile,
            macro_context=ctx.macro_context,
            signal_history_map=ctx.signal_history_map,
            account_size_hint=ctx.portfolio_account_size,
        )
