from __future__ import annotations

import unittest

from src.output.alert import evaluate_alert_rules
from src.types import CollectedTickerData, WatchlistItem


class AlertRulesTests(unittest.TestCase):
    def test_evaluate_alert_rules_matches_extended_numeric_fields(self) -> None:
        watchlist = [
            WatchlistItem(
                ticker="AAPL",
                name="Apple",
                alert_rules=[
                    {"condition": "price >= 180", "message": "breakout"},
                    {"condition": "change_percent > 2", "message": "strong day"},
                    {"condition": "relative_volume >= 1.5", "message": "volume surge"},
                    {"condition": "rsi >= 70", "message": "overbought"},
                    {"condition": "atr_percent > 3", "message": "volatile setup"},
                    {"condition": "rs_vs_spy > 5", "message": "relative strength"},
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
                relative_volume="1.67x",
                atr_percent="3.40%",
                rs_vs_spy="+8.20%",
                technical_indicators={"rsi_14": "72.1"},
            )
        }

        alerts = evaluate_alert_rules(watchlist, collected)

        self.assertEqual(
            alerts,
            [
                "AAPL: breakout",
                "AAPL: strong day",
                "AAPL: volume surge",
                "AAPL: overbought",
                "AAPL: volatile setup",
                "AAPL: relative strength",
            ],
        )


if __name__ == "__main__":
    unittest.main()
