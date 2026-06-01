from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.output.performance import write_performance_outputs
from src.output.strategy_simulator import write_strategy_simulator_output


class StrategySimulatorOutputTests(unittest.TestCase):
    def test_writes_strategy_simulator_json_and_web_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            output_root = project_root / "output"
            data_dir = output_root / "data"
            data_dir.mkdir(parents=True)
            (project_root / "web" / "public" / "output" / "data").mkdir(parents=True)
            _write_csv(
                data_dir / "signal_tracker.csv",
                ["signal_date", "ticker", "final_action", "conviction", "signal_direction", "llm_direction"],
                [["2026-04-01", "AAPL", "buy", "70", "bull", "bull"]],
            )
            _write_csv(
                data_dir / "price_history.csv",
                ["date", "ticker", "open", "high", "low", "close"],
                [
                    ["2026-04-01", "AAPL", "100", "101", "99", "100"],
                    ["2026-04-02", "AAPL", "101", "103", "100", "102"],
                ],
            )

            payload = write_strategy_simulator_output(output_root=output_root)

            path = data_dir / "strategy_simulator.json"
            mirror_path = project_root / "web" / "public" / "output" / "data" / "strategy_simulator.json"
            written = json.loads(path.read_text(encoding="utf-8"))
            mirrored = json.loads(mirror_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(set(payload["presets"]), {"conservative", "balanced", "aggressive"})
        self.assertEqual(written["basis"], "final_action")
        self.assertEqual(mirrored["mode"], "observational_long_only")

    def test_performance_output_regeneration_also_writes_strategy_simulator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            output_root = project_root / "output"
            data_dir = output_root / "data"
            logs_root = project_root / "logs" / "pipeline"
            data_dir.mkdir(parents=True)
            logs_root.mkdir(parents=True)
            (project_root / "web" / "public" / "output" / "data").mkdir(parents=True)
            _write_csv(
                data_dir / "signal_tracker.csv",
                ["signal_date", "ticker", "final_action", "conviction", "signal_direction", "llm_direction"],
                [["2026-04-01", "AAPL", "buy", "70", "bull", "bull"]],
            )
            _write_csv(
                data_dir / "price_history.csv",
                ["date", "ticker", "open", "high", "low", "close"],
                [
                    ["2026-04-01", "AAPL", "100", "101", "99", "100"],
                    ["2026-04-02", "AAPL", "101", "103", "100", "102"],
                ],
            )

            with (
                patch(
                    "src.output.performance.build_performance_payloads",
                    return_value=(
                        {
                            "status": "ok",
                            "latest_run_date": "2026-04-02",
                            "cost": {},
                            "quality": {},
                            "evidence": {},
                            "json_health": {},
                            "p1_readiness": {"tracks": {}},
                        },
                        {"runs": []},
                    ),
                ),
                patch(
                    "src.output.performance.build_quality_reliability_loop_payload",
                    return_value={"status": "ok", "summary": {}},
                ),
            ):
                result = write_performance_outputs(
                    output_root=output_root,
                    logs_root=logs_root,
                    project_root=project_root,
                )

            path = data_dir / "strategy_simulator.json"
            mirror_path = project_root / "web" / "public" / "output" / "data" / "strategy_simulator.json"
            path_exists = path.exists()
            mirror_path_exists = mirror_path.exists()

        self.assertEqual(result["strategy_simulator_path"], path)
        self.assertTrue(path_exists)
        self.assertTrue(mirror_path_exists)


def _write_csv(path: Path, fieldnames: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
