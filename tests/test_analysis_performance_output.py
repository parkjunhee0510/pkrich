from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.analysis_performance import write_analysis_performance_output
from src.output.schema import SCHEMA_VERSION
from src.types import MarketRegime, TickerDecision


class AnalysisPerformanceOutputTests(unittest.TestCase):
    def test_writes_analysis_performance_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            signal_rows = [
                {
                    "signal_date": "2026-04-30",
                    "ticker": "AAPL",
                    "action": "watch",
                    "conviction": "58",
                    "regime": "neutral",
                    "factors_json": '{"momentum": 0.2}',
                    "confidence_meta_json": '{"data_quality_score": 0.55}',
                    "return_1d": "+1.00%",
                    "return_5d": "+2.00%",
                    "return_20d": "N/A",
                    "evaluated_1d": "True",
                    "evaluated_5d": "True",
                    "evaluated_20d": "False",
                    "barrier_label": "hit",
                }
            ]

            payload = write_analysis_performance_output(
                output_root=output_root,
                run_date=date(2026, 5, 1),
                decisions=[
                    TickerDecision(
                        ticker="AAPL",
                        action="buy",
                        conviction=68,
                        factors={"momentum": 1.2},
                        confidence_meta={"data_quality_score": 0.80},
                    )
                ],
                market_regime=MarketRegime(regime="risk_on"),
                signal_rows=signal_rows,
            )

            path = output_root / "data" / "analysis_performance.json"
            written = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["as_of"], "2026-05-01")
        self.assertIn("signal_performance", payload)
        self.assertIn("conviction_calibration", payload)
        self.assertIn("regime_performance", payload)
        self.assertIn("factor_attribution", payload)
        self.assertEqual(payload["action_change_reasons"][0]["ticker"], "AAPL")
        self.assertEqual(written["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
