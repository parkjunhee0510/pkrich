from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from src.output.json_export import _sync_web_public_data, _write_validation_warnings_json


def _write_summary(logs_root: Path, day: date, **quality: int) -> None:
    logs_root.mkdir(parents=True, exist_ok=True)
    path = logs_root / f"{day.isoformat()}.summary.json"
    path.write_text(
        json.dumps({
            "run_date": day.isoformat(),
            "analyzer_quality": quality,
        }),
        encoding="utf-8",
    )


class ValidationWarningsExportTests(unittest.TestCase):
    def test_empty_logs_produce_zeroed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            original_cwd = os.getcwd()
            os.chdir(tmp_path)
            try:
                _write_validation_warnings_json(data_dir)
            finally:
                os.chdir(original_cwd)
            payload = json.loads((data_dir / "validation_warnings.json").read_text())
            self.assertEqual(payload["series"], [])
            self.assertEqual(payload["totals"]["fact_warning_count"], 0)

    def test_aggregates_recent_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            logs_root = tmp_path / "logs" / "pipeline"
            today = date.today()
            _write_summary(
                logs_root,
                today,
                fact_warning_count=3,
                hallucination_warning_count=1,
                validated_ticker_count=20,
                batch_count=2,
            )
            _write_summary(
                logs_root,
                today - timedelta(days=1),
                fact_warning_count=1,
                dropped_unsupported_count=2,
                validated_ticker_count=18,
                batch_count=2,
            )
            original_cwd = os.getcwd()
            os.chdir(tmp_path)
            try:
                _write_validation_warnings_json(data_dir, window_days=7)
            finally:
                os.chdir(original_cwd)
            payload = json.loads((data_dir / "validation_warnings.json").read_text())
            self.assertEqual(payload["totals"]["fact_warning_count"], 4)
            self.assertEqual(payload["totals"]["hallucination_warning_count"], 1)
            self.assertEqual(payload["totals"]["dropped_unsupported_count"], 2)
            self.assertEqual(len(payload["series"]), 2)
            # Series is oldest → newest.
            self.assertEqual(payload["series"][-1]["date"], today.isoformat())

    def test_corrupt_summary_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            logs_root = tmp_path / "logs" / "pipeline"
            logs_root.mkdir(parents=True)
            today = date.today()
            (logs_root / f"{today.isoformat()}.summary.json").write_text("not json", encoding="utf-8")
            original_cwd = os.getcwd()
            os.chdir(tmp_path)
            try:
                _write_validation_warnings_json(data_dir, window_days=3)
            finally:
                os.chdir(original_cwd)
            payload = json.loads((data_dir / "validation_warnings.json").read_text())
            # Corrupt file silently skipped — series just empty for that day.
            self.assertEqual(payload["series"], [])


    def test_validation_warnings_syncs_to_web_public_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            data_dir = project_root / "output" / "data"
            web_data_dir = project_root / "web" / "public" / "output" / "data"
            data_dir.mkdir(parents=True)
            (project_root / "web").mkdir()
            payload = {
                "schema_version": 1,
                "window_days": 14,
                "generated_at": "2026-05-04T00:00:00",
                "categories": {},
                "totals": {},
                "series": [],
            }
            source_path = data_dir / "validation_warnings.json"
            source_path.write_text(json.dumps(payload), encoding="utf-8")

            _sync_web_public_data(data_dir, project_root)

            mirror_path = web_data_dir / "validation_warnings.json"
            self.assertTrue(mirror_path.exists())
            self.assertEqual(source_path.read_bytes(), mirror_path.read_bytes())


class DroppedUnsupportedLoggerTests(unittest.TestCase):
    def test_dropped_unsupported_count_accumulates_into_summary(self) -> None:
        from src.utils.pipeline_logging import start_pipeline_logging, finalize_pipeline_logging, record_pipeline_event
        with tempfile.TemporaryDirectory() as tmp:
            logs_root = Path(tmp)
            start_pipeline_logging(date.today(), logs_root=logs_root)
            record_pipeline_event(
                "analyzer",
                "warning",
                "openai_response_validation_failed",
                ticker="AAPL",
                schema_violation_count=0,
                fact_warning_count=1,
                consistency_warning_count=0,
                hallucination_warning_count=0,
                dropped_unsupported_count=2,
            )
            summary_path = finalize_pipeline_logging(success=True)
            self.assertIsNotNone(summary_path)
            summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
            quality = summary["analyzer_quality"]
            self.assertEqual(quality.get("dropped_unsupported_count"), 2)
            self.assertEqual(quality.get("fact_warning_count"), 1)


if __name__ == "__main__":
    unittest.main()
