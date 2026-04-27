"""Integration tests for `run_policy_stage` (Task 8).

These tests guarantee graceful degradation: failures in the policy collector
or analyzer must NEVER raise out of the policy stage — the main pipeline
keeps running with policy data treated as missing.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.pipeline import run_policy_stage
from src.types import PolicyImpactReport


class TestRunPolicyStage(unittest.TestCase):
    @patch("src.pipeline.extract_events", return_value=[])
    @patch("src.pipeline.map_impacts")
    def test_returns_none_when_no_events(self, mock_map, _mock_extract):
        report = run_policy_stage(
            today="2026-04-27",
            ticker_ctx={},
            sources_config={},
            model_profile="deep",
            category_to_sectors={},
        )
        self.assertIsNone(report)
        mock_map.assert_not_called()

    @patch(
        "src.pipeline.extract_events",
        side_effect=RuntimeError("boom"),
    )
    def test_returns_none_on_collector_failure(self, _mock_extract):
        report = run_policy_stage(
            today="2026-04-27",
            ticker_ctx={},
            sources_config={},
            model_profile="deep",
            category_to_sectors={},
        )
        self.assertIsNone(report)

    @patch("src.pipeline.write_policy_impact_json")
    @patch("src.pipeline.map_impacts")
    @patch("src.pipeline.extract_events")
    def test_writes_json_when_events_present(
        self, mock_extract, mock_map, mock_write
    ):
        # Single sentinel event so extract returns truthy.
        mock_extract.return_value = [object()]
        fake_report = PolicyImpactReport(
            date="2026-04-27",
            events=[],
            impacts_by_event={},
            impacts_by_ticker={},
            tailwind_scores={"NVDA": 0.5},
            metadata={},
        )
        mock_map.return_value = fake_report

        report = run_policy_stage(
            today="2026-04-27",
            ticker_ctx={"NVDA": {}},
            sources_config={},
            model_profile="deep",
            category_to_sectors={},
            output_path="/tmp/never-written.json",
        )

        self.assertIs(report, fake_report)
        mock_write.assert_called_once()
        # First positional arg is the report.
        self.assertIs(mock_write.call_args.args[0], fake_report)


if __name__ == "__main__":
    unittest.main()
