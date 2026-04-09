from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.types import CollectedTickerData, PortfolioHolding
from src.utils.config import load_portfolio
from src.utils.portfolio import calculate_portfolio_summary


class PortfolioTests(unittest.TestCase):
    def test_load_portfolio_reads_holdings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / 'portfolio.yaml'
            config_path.write_text(
                '\n'.join(
                    [
                        'holdings:',
                        '  - ticker: AAPL',
                        '    shares: 10',
                        '    avg_cost: 150',
                        '    currency: USD',
                    ]
                ),
                encoding='utf-8',
            )

            holdings = load_portfolio(str(config_path))

        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0].ticker, 'AAPL')
        self.assertEqual(holdings[0].shares, 10.0)

    def test_calculate_portfolio_summary_returns_unrealized_pnl(self) -> None:
        holdings = [PortfolioHolding(ticker='AAPL', shares=10, avg_cost=150.0)]
        collected = {
            'AAPL': CollectedTickerData(
                ticker='AAPL',
                name='Apple Inc.',
                sector='Technology',
                price=180.0,
                change_percent=1.2,
                currency='USD',
                market_cap='1.00T',
                pe_ratio='25.00',
                summary_note='요약',
            )
        }

        summary = calculate_portfolio_summary(holdings, collected)

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.total_cost_basis, 1500.0)
        self.assertEqual(summary.total_market_value, 1800.0)
        self.assertEqual(summary.total_unrealized_pnl, 300.0)
        self.assertEqual(summary.total_unrealized_return_pct, 20.0)


if __name__ == '__main__':
    unittest.main()
