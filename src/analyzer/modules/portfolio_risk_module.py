from __future__ import annotations

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult
from src.utils.portfolio_risk import build_portfolio_risk_report


class PortfolioRiskModule(AnalysisModule):
    name = "portfolio_risk_module"
    requires = {"fundamentals", "historical_prices", "portfolio_summary"}
    produces = {"portfolio_risk"}
    priority = 5
    llm_required = False

    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        report = build_portfolio_risk_report(ctx.portfolio_summary, ctx.collected)
        diagnostics = {
            "has_portfolio_summary": ctx.portfolio_summary is not None,
            "positions": len(ctx.portfolio_summary.positions) if ctx.portfolio_summary else 0,
        }
        return ModuleResult(portfolio_result={"portfolio_risk": report}, diagnostics=diagnostics)
