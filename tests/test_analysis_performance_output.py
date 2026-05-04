from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.output.analysis_performance import write_analysis_performance_output
from src.output.schema import SCHEMA_VERSION
from src.types import MarketRegime, TickerDecision
from src.utils.signal_tracker import FIELDNAMES


class AnalysisPerformanceOutputTests(unittest.TestCase):
    def test_write_analysis_performance_output_reads_signal_tracker_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            csv_path = output_root / "data" / "signal_tracker.csv"
            csv_path.parent.mkdir(parents=True)
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerow(
                    {
                        "signal_date": "2026-04-30",
                        "ticker": "AAPL",
                        "signal_type": "takeaway",
                        "signal_direction": "bull",
                        "llm_direction": "bull",
                        "signal_price": "100.00",
                        "catalyst_tag": "earnings",
                        "news_tone": "bullish",
                        "trade_frame_scenario": "Margin expansion, services strength",
                        "conviction": "58",
                        "raw_conviction": "58",
                        "action": "watch",
                        "regime": "neutral",
                        "sub_regime": "",
                        "factors_json": json.dumps({"momentum": 0.2, "valuation": -0.1}),
                        "factor_reasoning_json": "{}",
                        "confidence_meta_json": json.dumps({"data_quality_score": 0.55}),
                        "return_1d": "+1.00%",
                        "return_5d": "+2.50%",
                        "return_20d": "N/A",
                        "evaluated_1d": "True",
                        "evaluated_5d": "True",
                        "evaluated_20d": "False",
                        "barrier_label": "take_profit",
                        "barrier_hit_day": "3",
                        "barrier_return": "+2.50%",
                        "barrier_date": "2026-05-01",
                    }
                )

            payload = write_analysis_performance_output(
                output_root=output_root,
                run_date=date(2026, 5, 1),
                decisions=[
                    TickerDecision(
                        ticker="AAPL",
                        action="buy",
                        conviction=68,
                        raw_conviction=68,
                        factors={"momentum": 1.4, "valuation": -0.2},
                        confidence_meta={"data_quality_score": 0.82},
                    )
                ],
                market_regime=MarketRegime(regime="risk_on"),
            )

            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            self.assertEqual(payload["as_of"], "2026-05-01")
            for key in (
                "signal_performance",
                "conviction_calibration",
                "regime_performance",
                "factor_attribution",
                "action_change_reasons",
            ):
                self.assertIn(key, payload)
            self.assertEqual(payload["action_change_reasons"][0]["ticker"], "AAPL")

            json_path = output_root / "data" / "analysis_performance.json"
            self.assertTrue(json_path.exists())
            written_payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(written_payload["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
