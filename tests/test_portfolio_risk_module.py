from __future__ import annotations

import unittest
from datetime import date, timedelta

from src.analyzer.base import AnalysisContext
from src.analyzer.modules.portfolio_risk_module import PortfolioRiskModule
from src.types import CollectedTickerData, PortfolioPosition, PortfolioSummary, WatchlistItem


def _historical_rows(start_price: float, step: float) -> list[dict[str, str]]:
    base = date(2026, 3, 1)
    rows: list[dict[str, str]] = []
    for index in range(35):
        price = start_price + (step * index)
        rows.append({"date": (base + timedelta(days=index)).isoformat(), "close": f"{price:.2f}", "price": f"{price:.2f}"})
    return rows


def _make_collected(ticker: str, sector: str, beta: str, start_price: float, step: float) -> CollectedTickerData:
    return CollectedTickerData(
        ticker=ticker,
        name=f"{ticker} Corp",
        sector=sector,
        price=start_price + (step * 34),
        change_percent=0.5,
        currency="USD",
        market_cap="10B",
        pe_ratio="20",
        summary_note="",
        atr_14d="4.0",
        fundamental_metrics={"beta": beta},
        historical_prices=_historical_rows(start_price, step),
    )


class PortfolioRiskModuleTests(unittest.TestCase):
    def test_module_returns_portfolio_risk_report_with_new_metrics(self) -> None:
        watchlist = [
            WatchlistItem(ticker="AAPL", name="Apple", sector="Technology"),
            WatchlistItem(ticker="MSFT", name="Microsoft", sector="Technology"),
        ]
        collected = {
            "AAPL": _make_collected("AAPL", "Technology", "1.20", 100.0, 0.8),
            "MSFT": _make_collected("MSFT", "Technology", "1.05", 80.0, 0.5),
        }
        portfolio_summary = PortfolioSummary(
            positions=[
                PortfolioPosition("AAPL", 10, 90.0, "USD", 127.2, 1272.0, 900.0, 372.0, 41.3),
                PortfolioPosition("MSFT", 8, 70.0, "USD", 97.0, 776.0, 560.0, 216.0, 38.6),
            ],
            total_market_value=2048.0,
            total_cost_basis=1460.0,
            total_unrealized_pnl=588.0,
            total_unrealized_return_pct=40.2,
        )
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map={},
            run_date=date(2026, 4, 16),
            portfolio_summary=portfolio_summary,
            available_inputs={"fundamentals", "historical_prices", "portfolio_summary"},
        )

        result = PortfolioRiskModule().analyze(ctx)
        report = result.portfolio_result["portfolio_risk"]
        self.assertIn("hhi", report)
        self.assertIn("portfolio_beta", report)
        self.assertIn("correlation_matrix", report)
        self.assertIn("mdd_20d", report)
        self.assertIn("var_95", report)
        self.assertIn("risk_grade", report)
        self.assertTrue(report["recommendations"])


if __name__ == "__main__":
    unittest.main()
