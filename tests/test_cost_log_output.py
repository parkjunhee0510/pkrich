from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.output.cost_log import write_cost_log_output
from src.output.schema import SCHEMA_VERSION


class CostLogOutputTests(unittest.TestCase):
    def test_writes_cost_log_with_profile_breakdown_and_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            logs_root = Path(temp_dir) / "logs" / "pipeline"
            logs_root.mkdir(parents=True, exist_ok=True)

            (logs_root / "2026-04-17.summary.json").write_text(
                json.dumps(
                    {
                        "run_date": "2026-04-17",
                        "success": True,
                        "daily_api_cost_usd": 0.42,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (logs_root / "2026-04-17.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "openai_usage_recorded",
                                "model_profile": "economy",
                                "model": "gpt-5.4-mini",
                                "estimated_cost_usd": 0.12,
                                "total_tokens": 1000,
                            }
                        ),
                        json.dumps(
                            {
                                "event": "openai_usage_recorded",
                                "model_profile": "deep",
                                "model": "o3-mini",
                                "estimated_cost_usd": 0.30,
                                "total_tokens": 2200,
                            }
                        ),
                        json.dumps(
                            {
                                "event": "decision_completed",
                                "ensemble_enabled": True,
                                "ensemble_eligible_count": 6,
                                "ensemble_selected_count": 3,
                                "ensemble_skipped_due_to_cap": 1,
                                "ensemble_conflicted_count": 2,
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            payload = write_cost_log_output(output_root=output_root, logs_root=logs_root)

            latest = payload["latest"]
            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            self.assertEqual(latest["run_date"], "2026-04-17")
            self.assertEqual(latest["profiles"]["economy"]["tokens"], 1000)
            self.assertAlmostEqual(latest["profiles"]["deep"]["cost_usd"], 0.30)
            self.assertEqual(latest["routing"]["selected_count"], 3)
            self.assertEqual(latest["deep_pass_value"]["selected_ticker_count"], 3)
            self.assertTrue((output_root / "data" / "cost_log.json").exists())


if __name__ == "__main__":
    unittest.main()
