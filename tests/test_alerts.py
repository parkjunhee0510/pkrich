from __future__ import annotations

import unittest

from src.output.alert import evaluate_alert_rules
from src.types import CollectedTickerData, WatchlistItem


class AlertRulesTests(unittest.TestCase):
    def test_evaluate_alert_rules_matches_price_and_change_percent(self) -> None:
        watchlist = [
            WatchlistItem(
                ticker="AAPL",
                name="Apple",
                alert_rules=[
                    {"condition": "price >= 180", "message": "breakout"},
                    {"condition": "change_percent > 2", "message": "strong day"},
                ],
            )
        ]
        collected = {
            "AAPL": CollectedTickerData(
                ticker="AAPL",
                name="Apple",
                sector="Technology",
                price=181.2,
                change_percent=2.4,
                currency="USD",
                market_cap="1T",
                pe_ratio="20",
                summary_note="steady",
                eps="5",
                week52_high="190",
                week52_low="150",
            )
        }

        alerts = evaluate_alert_rules(watchlist, collected)

        self.assertEqual(alerts, ["AAPL: breakout", "AAPL: strong day"])


if __name__ == "__main__":
    unittest.main()
