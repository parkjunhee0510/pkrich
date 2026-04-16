from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.output.analysis_quality import write_analysis_quality_output


class AnalysisQualityOutputTests(unittest.TestCase):
    def test_writes_analysis_quality_json_with_hallucination_ratio(self) -> None:
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

            self.assertEqual(payload["latest"]["run_date"], "2026-04-16")
            self.assertEqual(payload["latest"]["hallucination_ratio"], 0.2)
            self.assertTrue((output_root / "data" / "analysis_quality.json").exists())


if __name__ == "__main__":
    unittest.main()
