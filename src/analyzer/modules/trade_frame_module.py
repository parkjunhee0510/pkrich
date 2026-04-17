from __future__ import annotations

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult
from src.analyzer import research_note


class TradeFrameModule(AnalysisModule):
    name = "trade_frame_module"
    requires = {"price", "fundamentals", "upcoming_events", "quarterly_financials"}
    produces = {"trade_frame"}
    priority = 20
    llm_required = False

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        return ModuleResult(
            results_by_ticker={
                item.ticker: {
                    "trade_frame": research_note._build_fallback_trade_frame(
                        ctx.collected[item.ticker],
                        account_size_hint=ctx.portfolio_account_size,
                    )
                }
                for item in ctx.watchlist
            }
        )
