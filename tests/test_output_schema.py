from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.output.analysis_quality import write_analysis_quality_output
from src.output.api_status import build_api_status_payload
from src.output.cost_log import write_cost_log_output
from src.output.json_export import write_json_outputs
from src.output.schema import SCHEMA_VERSION
from src.types import TickerDecision, WatchlistItem
from tests.helpers.output_snapshot import load_snapshot_fixture, normalize_json_shape
from tests.test_output import _sample_analysis

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "output_schemas"


class OutputSchemaTests(unittest.TestCase):
    def test_dashboard_index_matches_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            write_json_outputs([_sample_analysis()], date(2026, 4, 8), output_root=output_root)
            payload = json.loads((output_root / "data" / "index.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "index.shape.json")
        self.assertEqual(normalize_json_shape(payload), expected)

    def test_dashboard_history_matches_shadow_decision_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            with patch.dict("os.environ", {"EMIT_LEGACY_DASHBOARD": "0"}, clear=False):
                write_json_outputs(
                    [_sample_analysis()],
                    date(2026, 4, 8),
                    output_root=output_root,
                    decisions=[
                        TickerDecision(
                            ticker="AAPL",
                            action="buy",
                            conviction=74,
                            raw_conviction=81,
                            reason="confidence shadow",
                            valid_until="2026-04-15",
                            factors={"momentum": 12.0},
                            confidence_meta={
                                "confidence_gate": 0.75,
                                "data_quality": 0.9,
                                "evidence_coverage": 0.8,
                                "evidence_consistency": 0.7,
                                "model_agreement": 0.85,
                            },
                        )
                    ],
                )
            payload = json.loads((output_root / "data" / "dashboard_history.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "dashboard_with_confidence.shape.json")
        self.assertEqual(normalize_json_shape(payload), expected)

    def test_api_status_json_matches_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logs_root = root / "logs" / "pipeline"
            output_root = root / "output"
            logs_root.mkdir(parents=True, exist_ok=True)
            (output_root / "data").mkdir(parents=True, exist_ok=True)
            (logs_root / "2026-04-13.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "pipeline_started", "component": "pipeline", "level": "info"}),
                        json.dumps({"event": "data_provider_used", "component": "collector", "level": "info", "ticker": "AAPL", "source": "yfinance"}),
                        json.dumps({"event": "pipeline_completed", "component": "pipeline", "level": "info"}),
                    ]
                ),
                encoding="utf-8",
            )
            payload = build_api_status_payload(
                date(2026, 4, 13),
                [WatchlistItem(ticker="AAPL", name="Apple Inc.")],
                logs_root=logs_root,
                output_root=output_root,
            )["summary"]

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "api_status.shape.json")
        self.assertEqual(normalize_json_shape(payload), expected)

    def test_analysis_quality_json_matches_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            logs_root = Path(temp_dir) / "logs" / "pipeline"
            logs_root.mkdir(parents=True, exist_ok=True)
            (logs_root / "2026-04-16.summary.json").write_text(
                json.dumps(
                    {
                        "run_date": "2026-04-16",
                        "success": True,
                        "daily_api_cost_usd": 0.42,
                        "analyzer_quality": {
                            "batch_count": 4,
                            "validated_ticker_count": 10,
                            "validation_failure_count": 2,
                            "schema_violation_count": 1,
                            "fact_warning_count": 1,
                            "consistency_warning_count": 0,
                            "hallucination_warning_count": 2,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = write_analysis_quality_output(output_root=output_root, logs_root=logs_root)

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "analysis_quality.shape.json")
        self.assertEqual(normalize_json_shape(payload), expected)

    def test_cost_log_json_matches_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            logs_root = Path(temp_dir) / "logs" / "pipeline"
            logs_root.mkdir(parents=True, exist_ok=True)
            (logs_root / "2026-04-17.summary.json").write_text(
                json.dumps({"run_date": "2026-04-17", "success": True, "daily_api_cost_usd": 0.42}, ensure_ascii=False),
                encoding="utf-8",
            )
            (logs_root / "2026-04-17.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "openai_usage_recorded", "model_profile": "economy", "model": "gpt-5.4-mini", "estimated_cost_usd": 0.12, "input_tokens": 800, "cached_input_tokens": 600, "total_tokens": 1000}),
                        json.dumps({"event": "openai_usage_recorded", "model_profile": "deep", "model": "o3-mini", "estimated_cost_usd": 0.30, "input_tokens": 1000, "cached_input_tokens": 250, "total_tokens": 2200}),
                        json.dumps({"event": "decision_completed", "ensemble_enabled": True, "ensemble_eligible_count": 6, "ensemble_selected_count": 3, "ensemble_skipped_due_to_cap": 1, "ensemble_conflicted_count": 2}),
                    ]
                ),
                encoding="utf-8",
            )
            payload = write_cost_log_output(output_root=output_root, logs_root=logs_root)

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "cost_log.shape.json")
        self.assertEqual(normalize_json_shape(payload), expected)


if __name__ == "__main__":
    unittest.main()
