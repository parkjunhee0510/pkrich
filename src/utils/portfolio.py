from __future__ import annotations

from src.types import CollectedTickerData, PortfolioHolding, PortfolioPosition, PortfolioSummary


def calculate_portfolio_summary(
    holdings: list[PortfolioHolding],
    collected_data: dict[str, CollectedTickerData],
) -> PortfolioSummary | None:
    if not holdings:
        return None

    positions: list[PortfolioPosition] = []
    known_market_value_total = 0.0
    total_cost_basis = 0.0
    all_prices_known = True

    for holding in holdings:
        collected = collected_data.get(holding.ticker)
        market_price = collected.price if collected is not None else None
        cost_basis = holding.shares * holding.avg_cost
        market_value = holding.shares * market_price if market_price is not None else None
        unrealized_pnl = (market_value - cost_basis) if market_value is not None else None
        unrealized_return_pct = ((unrealized_pnl / cost_basis) * 100) if unrealized_pnl is not None and cost_basis else None

        total_cost_basis += cost_basis
        if market_value is None:
            all_prices_known = False
        else:
            known_market_value_total += market_value

        positions.append(
            PortfolioPosition(
                ticker=holding.ticker,
                shares=holding.shares,
                avg_cost=holding.avg_cost,
                currency=holding.currency,
                market_price=market_price,
                market_value=market_value,
                cost_basis=cost_basis,
                unrealized_pnl=unrealized_pnl,
                unrealized_return_pct=unrealized_return_pct,
            )
        )

    total_market_value = known_market_value_total if all_prices_known else None
    total_unrealized_pnl = (total_market_value - total_cost_basis) if total_market_value is not None else None
    total_unrealized_return_pct = (
        (total_unrealized_pnl / total_cost_basis) * 100
        if total_unrealized_pnl is not None and total_cost_basis
        else None
    )

    return PortfolioSummary(
        positions=positions,
        total_market_value=total_market_value,
        total_cost_basis=total_cost_basis,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_return_pct=total_unrealized_return_pct,
    )
