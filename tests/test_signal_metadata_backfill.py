from __future__ import annotations

import csv
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src.cli.backfill_signal_metadata import main
from src.utils.signal_metadata_backfill import (
    backfill_signal_metadata_file,
    backfill_signal_metadata_rows,
)


def _history_payload() -> dict:
    return {
        "schema_version": 1,
        "days": [
            {
                "date": "2026-05-01",
                "market_regime": {"regime": "risk_on", "sub_regime": "growth"},
                "tickers": [
                    {
                        "ticker": "AAPL",
                        "decision": {
                            "action": "buy",
                            "conviction": 72,
                            "raw_conviction": 80,
                            "factors": {"momentum": 1.5},
                            "factor_reasoning": {"momentum": "trend improved"},
                            "confidence_meta": {"data_quality_score": 0.88},
                        },
                    }
                ],
            }
        ],
    }


class SignalMetadataBackfillTests(unittest.TestCase):
    def test_backfills_missing_metadata_from_dashboard_history(self) -> None:
        rows = [
            {
                "signal_date": "2026-05-01",
                "ticker": "AAPL",
                "action": "",
                "conviction": "",
                "raw_conviction": "",
                "regime": "",
                "sub_regime": "",
                "factors_json": "",
                "factor_reasoning_json": "",
                "confidence_meta_json": "",
            }
        ]

        result = backfill_signal_metadata_rows(rows, _history_payload())

        self.assertEqual(result.stats["matched_rows"], 1)
        self.assertEqual(result.stats["updated_rows"], 1)
        self.assertEqual(result.rows[0]["action"], "buy")
        self.assertEqual(result.rows[0]["conviction"], "72")
        self.assertEqual(result.rows[0]["raw_conviction"], "80")
        self.assertEqual(result.rows[0]["regime"], "risk_on")
        self.assertEqual(result.rows[0]["sub_regime"], "growth")
        self.assertEqual(json.loads(result.rows[0]["factors_json"]), {"momentum": 1.5})
        self.assertEqual(json.loads(result.rows[0]["factor_reasoning_json"]), {"momentum": "trend improved"})
        self.assertEqual(json.loads(result.rows[0]["confidence_meta_json"]), {"data_quality_score": 0.88})

    def test_preserves_existing_metadata(self) -> None:
        rows = [
            {
                "signal_date": "2026-05-01",
                "ticker": "AAPL",
                "action": "watch",
                "conviction": "55",
                "factors_json": "{\"existing\": 1}",
            }
        ]

        result = backfill_signal_metadata_rows(rows, _history_payload())

        self.assertEqual(result.stats["matched_rows"], 1)
        self.assertEqual(result.stats["updated_rows"], 1)
        self.assertEqual(result.rows[0]["action"], "watch")
        self.assertEqual(result.rows[0]["conviction"], "55")
        self.assertEqual(json.loads(result.rows[0]["factors_json"]), {"existing": 1})
        self.assertEqual(result.rows[0]["raw_conviction"], "80")

    def test_backfill_file_rewrites_csv_with_metadata_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "signal_tracker.csv"
            history_path = root / "dashboard_history.json"
            csv_path.write_text(
                "signal_date,ticker,signal_type,signal_direction,llm_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d\n"
                "2026-05-01,AAPL,takeaway,bull,bull,100,earnings,bullish,base,N/A,N/A,N/A,False,False,False\n",
                encoding="utf-8",
            )
            history_path.write_text(json.dumps(_history_payload()), encoding="utf-8")

            stats = backfill_signal_metadata_file(csv_path, history_path)
            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(stats["updated_rows"], 1)
        self.assertEqual(rows[0]["action"], "buy")
        self.assertEqual(rows[0]["regime"], "risk_on")
        self.assertEqual(json.loads(rows[0]["factors_json"]), {"momentum": 1.5})

    def test_cli_backfills_default_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "output" / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "signal_tracker.csv").write_text(
                "signal_date,ticker,signal_type,signal_direction,llm_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d\n"
                "2026-05-01,AAPL,takeaway,bull,bull,100,earnings,bullish,base,N/A,N/A,N/A,False,False,False\n",
                encoding="utf-8",
            )
            (data_dir / "dashboard_history.json").write_text(json.dumps(_history_payload()), encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--project-root", str(root)])
            with (data_dir / "signal_tracker.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(exit_code, 0)
        self.assertEqual(rows[0]["action"], "buy")


if __name__ == "__main__":
    unittest.main()
