from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.output.routing_outcome import write_routing_outcome_output
from src.output.schema import SCHEMA_VERSION


class RoutingOutcomeOutputTests(unittest.TestCase):
    def test_writes_summary_and_period_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            data_dir = output_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            (data_dir / "routing_log_history.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "runs": [
                            {
                                "run_date": "2026-04-01",
                                "trigger_range": [25, 75],
                                "max_daily_ensemble": 0,
                                "portfolio_priority": True,
                                "deep_pass_count": 2,
                                "tickers": [
                                    {
                                        "ticker": "AAPL",
                                        "selected_for_deep": True,
                                        "reason": "in_trigger_range",
                                        "in_portfolio": False,
                                        "conviction": 60,
                                        "action": "buy",
                                    },
                                    {
                                        "ticker": "MSFT",
                                        "selected_for_deep": False,
                                        "reason": "below_range",
                                        "in_portfolio": False,
                                        "conviction": 20,
                                        "action": "watch",
                                    },
                                    {
                                        "ticker": "KO",
                                        "selected_for_deep": True,
                                        "reason": "portfolio_priority",
                                        "in_portfolio": True,
                                        "conviction": 15,
                                        "action": "watch",
                                    },
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            signal_rows = [
                {
                    "signal_date": "2026-04-01",
                    "ticker": "AAPL",
                    "signal_type": "swing",
                    "signal_direction": "bull",
                    "signal_price": "100",
                    "catalyst_tag": "earnings",
                    "news_tone": "bullish",
                    "trade_frame_scenario": "bull",
                    "return_1d": "1.0%",
                    "return_5d": "2.0%",
                    "return_20d": "10.0%",
                    "evaluated_1d": "true",
                    "evaluated_5d": "true",
                    "evaluated_20d": "true",
                },
                {
                    "signal_date": "2026-04-01",
                    "ticker": "MSFT",
                    "signal_type": "swing",
                    "signal_direction": "bull",
                    "signal_price": "100",
                    "catalyst_tag": "macro",
                    "news_tone": "neutral",
                    "trade_frame_scenario": "base",
                    "return_1d": "0.0%",
                    "return_5d": "1.0%",
                    "return_20d": "4.0%",
                    "evaluated_1d": "true",
                    "evaluated_5d": "true",
                    "evaluated_20d": "true",
                },
                {
                    "signal_date": "2026-04-01",
                    "ticker": "KO",
                    "signal_type": "swing",
                    "signal_direction": "bull",
                    "signal_price": "100",
                    "catalyst_tag": "portfolio",
                    "news_tone": "neutral",
                    "trade_frame_scenario": "base",
                    "return_1d": "-1.0%",
                    "return_5d": "0.5%",
                    "return_20d": "-2.0%",
                    "evaluated_1d": "true",
                    "evaluated_5d": "true",
                    "evaluated_20d": "true",
                },
            ]

            fake_datastore = type(
                "FakeDatastore",
                (),
                {"load_signal_rows_data": lambda self: signal_rows},
            )()

            with patch("src.output.routing_outcome.get_datastore", return_value=fake_datastore):
                payload = write_routing_outcome_output(output_root=output_root)

            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["evaluated_signals"], 3)
            self.assertEqual(payload["summary"]["deep_selected_count"], 2)
            self.assertEqual(payload["summary"]["economy_only_count"], 1)
            self.assertEqual(payload["summary"]["deep_selected_avg_return_20d"], 4.0)
            self.assertEqual(payload["summary"]["economy_only_avg_return_20d"], 4.0)
            self.assertEqual(payload["summary"]["portfolio_priority_count"], 1)
            self.assertEqual(payload["summary"]["portfolio_priority_avg_return_20d"], -2.0)
            self.assertEqual(payload["summary"]["portfolio_priority_hit_rate"], 0.0)
            self.assertEqual(payload["periods"][0]["period"], "2026-04")
            self.assertEqual(payload["latest_run"]["deep_pass_count"], 2)
            self.assertTrue((data_dir / "routing_outcome.json").exists())


if __name__ == "__main__":
    unittest.main()
