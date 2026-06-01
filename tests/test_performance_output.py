from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.output.performance import write_performance_outputs


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class PerformanceOutputTests(unittest.TestCase):
    def test_write_performance_outputs_defaults_to_budget_guard_monthly_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "output"
            logs_root = root / "logs" / "pipeline"
            (root / "config").mkdir(parents=True)
            (root / "config" / "models.yaml").write_text(
                "\n".join(
                    [
                        "budget_guard:",
                        "  monthly_cap_usd: 4.5",
                    ]
                ),
                encoding="utf-8",
            )
            _write_json(
                output_root / "data" / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "total_cost_usd": 0.1,
                        "profiles": {"economy": {"calls": 1}},
                    },
                    "runs": [],
                },
            )
            _write_json(
                output_root / "data" / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {"run_date": "2026-05-07"},
                    "runs": [],
                },
            )

            write_performance_outputs(
                output_root=output_root,
                logs_root=logs_root,
                project_root=root,
                run_date=date(2026, 5, 7),
            )

            baseline = json.loads(
                (output_root / "data" / "performance_baseline.json").read_text(encoding="utf-8")
            )

        self.assertEqual(baseline["monthly_budget_usd"], 4.5)
        self.assertEqual(baseline["cost"]["monthly_budget_usd"], 4.5)
        self.assertEqual(baseline["cost"]["estimated_monthly_cost_usd"], 2.2)
        self.assertEqual(baseline["cost"]["budget_usage_ratio"], 0.4889)

    def test_write_performance_outputs_writes_json_markdown_and_web_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "output"
            logs_root = root / "logs" / "pipeline"
            web_public = root / "web" / "public" / "output" / "data"
            web_public.mkdir(parents=True)
            _write_json(
                output_root / "data" / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "total_cost_usd": 0.43,
                        "profiles": {"economy": {"calls": 1}},
                        "budget_guard": {
                            "mode": "shadow",
                            "decision_counts": {"would_block": 1},
                            "would_block_count": 1,
                            "blocked_count": 0,
                            "guarded_paths": {"ensemble_deep": "would_block"},
                            "total_estimated_incremental_cost_usd": 0.28,
                        },
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-07",
                            "success": True,
                            "total_cost_usd": 0.43,
                            "profiles": {"economy": {"calls": 1}},
                        }
                    ],
                },
            )
            _write_json(
                output_root / "data" / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "validated_ticker_count": 10,
                        "hallucination_ratio": 0.1,
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-07",
                            "validated_ticker_count": 10,
                            "hallucination_ratio": 0.1,
                        }
                    ],
                },
            )
            _write_json(
                output_root / "data" / "search_evidence.json",
                {
                    "schema_version": 1,
                    "provider": "cache",
                    "by_ticker": {
                        "AAPL": {
                            "evidence_count": 2,
                            "coverage_score": 0.8,
                            "freshness_score": 0.9,
                            "evidence_status": "covered",
                            "cache_age_hours": 0,
                        },
                        "AMD": {
                            "evidence_count": 0,
                            "coverage_score": 0.0,
                            "freshness_score": 0.0,
                            "evidence_status": "provider_unavailable",
                            "cache_age_hours": 0,
                        },
                    },
                    "run_summary": {
                        "candidate_ticker_count": 2,
                        "searched_ticker_count": 1,
                        "cache_hit_count": 1,
                        "stale_cache_hit_count": 0,
                        "cache_ttl_hours": 24,
                        "priority_tickers": ["AAPL", "AMD"],
                        "priority_ticker_count": 2,
                        "provider_candidate_count": 1,
                        "provider_call_count": 0,
                        "provider_error_count": 0,
                        "cache_error_count": 0,
                        "skipped_ticker_count": 1,
                        "status_counts": {
                            "covered": 1,
                            "provider_unavailable": 1,
                        },
                    },
                },
            )
            _write_json(
                output_root / "data" / "analysis_performance.json",
                {
                    "schema_version": 1,
                    "summary": {
                        "sample_count": 5,
                        "decision_count": 2,
                        "completed_return_windows": ["1d"],
                        "mode": "shadow_observational",
                    },
                    "signal_performance": {
                        "buy": {"1d": {"completed_count": 2}},
                        "watch": {"1d": {"completed_count": 1}},
                    },
                    "conviction_calibration": {
                        "status": "observational",
                        "buckets": {"50_65": {"sample_count": 3}},
                    },
                    "regime_performance": {"risk_on": {}},
                    "factor_attribution": {
                        "status": "observed_association",
                        "missing_factor_sample_count": 1,
                        "factors": {"momentum": {"sample_count": 3}},
                    },
                    "action_change_reasons": [],
                },
            )

            result = write_performance_outputs(
                output_root=output_root,
                logs_root=logs_root,
                project_root=root,
                run_date=date(2026, 5, 7),
            )

            baseline_path = output_root / "data" / "performance_baseline.json"
            trends_path = output_root / "data" / "performance_trends.json"
            quality_loop_path = output_root / "data" / "quality_reliability_loop.json"
            report_path = root / "docs" / "reports" / "performance-2026-05-07.md"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            trends = json.loads(trends_path.read_text(encoding="utf-8"))
            quality_loop = json.loads(quality_loop_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            report_exists = report_path.exists()
            baseline_mirror_exists = (web_public / "performance_baseline.json").exists()
            trends_mirror_exists = (web_public / "performance_trends.json").exists()
            quality_loop_mirror_exists = (
                web_public / "quality_reliability_loop.json"
            ).exists()

        self.assertEqual(result["baseline_path"], baseline_path)
        self.assertEqual(result["trends_path"], trends_path)
        self.assertEqual(result["quality_loop_path"], quality_loop_path)
        self.assertEqual(result["report_path"], report_path)
        self.assertEqual(baseline["schema_version"], 1)
        self.assertEqual(trends["schema_version"], 1)
        self.assertEqual(quality_loop["schema_version"], 1)
        self.assertEqual(quality_loop["summary"]["cost_status"], "reported")
        self.assertEqual(quality_loop["cost_and_runtime"]["cost_policy"], "report_only")
        self.assertTrue(report_exists)
        self.assertTrue(baseline_mirror_exists)
        self.assertTrue(trends_mirror_exists)
        self.assertTrue(quality_loop_mirror_exists)
        self.assertIn("- Priority evidence coverage: `0.5`", report_text)
        self.assertIn("- Priority evidence statuses: `covered=1, provider_unavailable=1`", report_text)
        self.assertIn("- Evidence cache hit ratio: `0.5`", report_text)
        self.assertIn("- Stale cache hits: `0/1`", report_text)
        self.assertIn("- Average cache age hours: `0.0`", report_text)
        self.assertIn("## Quality Reliability Loop", report_text)
        self.assertIn("- Quality loop status:", report_text)
        self.assertIn("- Cost policy: `report_only`", report_text)
        self.assertIn("## P1 Readiness", report_text)
        self.assertIn("- Overall status: `ready`", report_text)
        self.assertIn("- Search evidence provider: `ready_for_limited_provider_validation`", report_text)
        self.assertIn("- Search provider cap: `priority_queued_within_cap`", report_text)
        self.assertIn("- Search provider issues: `provider_unavailable_seen`", report_text)
        self.assertIn("- Search provider calls: `0`", report_text)
        self.assertIn("- Search stale cache: `no_stale_cache_reuse`", report_text)
        self.assertIn("- BudgetGuard: `report_ready`", report_text)
        self.assertIn("- BudgetGuard review: `report_only_review_required`", report_text)
        self.assertIn("- BudgetGuard would-block paths: `1/1`", report_text)
        self.assertIn("- BudgetGuard blocked paths: `0`", report_text)
        self.assertIn("- BudgetGuard estimated incremental cost: `$0.28`", report_text)
        self.assertIn("- Analysis performance: `ready`", report_text)
        self.assertIn("- Analysis loop: `ready_for_quality_review`", report_text)
        self.assertIn("- Analysis completed windows: `1`", report_text)
        self.assertIn("- Analysis evaluated signal windows: `2`", report_text)
        self.assertIn("- Analysis factors tracked: `1`", report_text)
        self.assertIn("- Analysis action-change coverage: `0.0`", report_text)
        self.assertIn("- Output schema: `ready`", report_text)

    def test_write_performance_outputs_syncs_quality_loop_to_existing_dist_mirror(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "output"
            logs_root = root / "logs" / "pipeline"
            web_dist = root / "web" / "dist" / "output" / "data"
            web_dist.mkdir(parents=True)

            result = write_performance_outputs(
                output_root=output_root,
                logs_root=logs_root,
                project_root=root,
                run_date=date(2026, 5, 7),
            )

            quality_loop_path = result["quality_loop_path"]
            quality_loop_dist_path = web_dist / "quality_reliability_loop.json"
            quality_loop_text = quality_loop_path.read_text(encoding="utf-8")
            quality_loop_dist_text = quality_loop_dist_path.read_text(encoding="utf-8")
            quality_loop_dist_exists = quality_loop_dist_path.exists()

        self.assertTrue(quality_loop_dist_exists)
        self.assertEqual(quality_loop_text, quality_loop_dist_text)

    def test_write_performance_outputs_keeps_source_when_web_sync_copy_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "output"
            logs_root = root / "logs" / "pipeline"
            web_public = root / "web" / "public" / "output" / "data"
            web_public.mkdir(parents=True)

            with patch(
                "src.output.json_export.shutil.copy2",
                side_effect=PermissionError("locked"),
            ) as mock_copy:
                result = write_performance_outputs(
                    output_root=output_root,
                    logs_root=logs_root,
                    project_root=root,
                    run_date=date(2026, 5, 7),
                )

            quality_loop_path = result["quality_loop_path"]
            quality_loop_exists = quality_loop_path.exists()
            copy_attempt_count = mock_copy.call_count

        self.assertTrue(quality_loop_exists)
        self.assertGreater(copy_attempt_count, 0)


if __name__ == "__main__":
    unittest.main()
