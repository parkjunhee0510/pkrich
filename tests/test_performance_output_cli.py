from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class PerformanceOutputCliTests(unittest.TestCase):
    def test_cli_writes_performance_outputs_from_project_root(self) -> None:
        from src.cli.write_performance_outputs import main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_data = root / "output" / "data"
            web_public = root / "web" / "public" / "output" / "data"
            web_public.mkdir(parents=True)
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
                output_data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "total_cost_usd": 0.43,
                        "profiles": {"economy": {"calls": 2}},
                        "watchlist_ticker_count": 4,
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-07",
                            "success": True,
                            "total_cost_usd": 0.43,
                            "profiles": {"economy": {"calls": 2}},
                        }
                    ],
                },
            )
            _write_json(
                output_data / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "validated_ticker_count": 4,
                        "hallucination_ratio": 0.0,
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-07",
                            "validated_ticker_count": 4,
                            "hallucination_ratio": 0.0,
                        }
                    ],
                },
            )
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["--project-root", str(root), "--run-date", "2026-05-07"])

            baseline_path = output_data / "performance_baseline.json"
            trends_path = output_data / "performance_trends.json"
            quality_loop_path = output_data / "quality_reliability_loop.json"
            strategy_simulator_path = output_data / "strategy_simulator.json"
            report_path = root / "docs" / "reports" / "performance-2026-05-07.md"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            trends = json.loads(trends_path.read_text(encoding="utf-8"))
            quality_loop = json.loads(quality_loop_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())
            report_exists = report_path.exists()
            strategy_simulator_exists = strategy_simulator_path.exists()
            baseline_text = baseline_path.read_text(encoding="utf-8")
            baseline_mirror_text = (web_public / "performance_baseline.json").read_text(
                encoding="utf-8"
            )
            trends_text = trends_path.read_text(encoding="utf-8")
            trends_mirror_text = (web_public / "performance_trends.json").read_text(
                encoding="utf-8"
            )
            quality_loop_text = quality_loop_path.read_text(encoding="utf-8")
            quality_loop_mirror_text = (
                web_public / "quality_reliability_loop.json"
            ).read_text(encoding="utf-8")
            strategy_simulator_mirror_exists = (
                web_public / "strategy_simulator.json"
            ).exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(baseline["status"], "ok")
        self.assertEqual(baseline["as_of"], "2026-05-07")
        self.assertEqual(baseline["monthly_budget_usd"], 4.5)
        self.assertEqual(baseline["cost"]["monthly_budget_usd"], 4.5)
        self.assertEqual(trends["runs"][0]["run_date"], "2026-05-07")
        self.assertEqual(quality_loop["schema_version"], 1)
        self.assertEqual(quality_loop["summary"]["cost_status"], "reported")
        self.assertTrue(report_exists)
        self.assertEqual(baseline_text, baseline_mirror_text)
        self.assertEqual(trends_text, trends_mirror_text)
        self.assertEqual(quality_loop_text, quality_loop_mirror_text)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["latest_run_date"], "2026-05-07")
        self.assertEqual(summary["baseline_path"], str(baseline_path))
        self.assertEqual(summary["trends_path"], str(trends_path))
        self.assertEqual(summary["quality_loop_path"], str(quality_loop_path))
        self.assertEqual(summary["strategy_simulator_path"], str(strategy_simulator_path))
        self.assertEqual(summary["report_path"], str(report_path))
        self.assertTrue(strategy_simulator_exists)
        self.assertTrue(strategy_simulator_mirror_exists)


if __name__ == "__main__":
    unittest.main()
