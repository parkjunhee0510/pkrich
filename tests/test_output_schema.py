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
from src.types import PortfolioPosition, PortfolioSummary, TickerAnalysis, TickerDecision, WatchlistItem
from tests.helpers.output_snapshot import load_snapshot_fixture, normalize_json_shape
from tests.test_output import _sample_analysis

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "output_schemas"


def _pm_schema_analyses() -> list[TickerAnalysis]:
    held = _sample_analysis()
    candidate = TickerAnalysis(
        **{
            **held.__dict__,
            "ticker": "MSFT",
            "name": "Microsoft Corp.",
            "summary": "MSFT summary",
            "signal_or_takeaway": "monitor",
            "upcoming_events": [],
        }
    )
    return [held, candidate]


def _pm_schema_decisions() -> list[TickerDecision]:
    return [
        TickerDecision(
            ticker="AAPL",
            action="watch",
            conviction=58,
            reason="held under review",
            valid_until="2026-04-15",
            factors={},
        ),
        TickerDecision(
            ticker="MSFT",
            action="buy",
            conviction=82,
            reason="candidate buy",
            valid_until="2026-04-15",
            factors={},
        ),
    ]


def _pm_schema_portfolio() -> PortfolioSummary:
    return PortfolioSummary(
        positions=[
            PortfolioPosition(
                ticker="AAPL",
                shares=10,
                avg_cost=90.0,
                currency="USD",
                market_price=100.0,
                market_value=1000.0,
                cost_basis=900.0,
                unrealized_pnl=100.0,
                unrealized_return_pct=11.11,
            )
        ],
        total_market_value=1000.0,
        total_cost_basis=900.0,
        total_unrealized_pnl=100.0,
        total_unrealized_return_pct=11.11,
    )


class OutputSchemaTests(unittest.TestCase):
    def test_dashboard_legacy_matches_snapshot_shape_with_pm_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            with patch.dict("os.environ", {"EMIT_LEGACY_DASHBOARD": "1"}, clear=False):
                write_json_outputs(
                    [_sample_analysis()],
                    date(2026, 4, 8),
                    output_root=output_root,
                    decisions=[
                        TickerDecision(
                            ticker="AAPL",
                            action="watch",
                            conviction=74,
                            reason="pm decision path",
                            valid_until="2026-04-15",
                            factors={},
                        )
                    ],
                )
            payload = json.loads((output_root / "data" / "dashboard.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "dashboard.shape.json")
        self.assertEqual(normalize_json_shape(payload), expected)

    def test_dashboard_index_matches_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            write_json_outputs([_sample_analysis()], date(2026, 4, 8), output_root=output_root)
            payload = json.loads((output_root / "data" / "index.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertIn("pm_view", payload)
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
                            action="watch",
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

    def test_dashboard_history_pm_view_matches_populated_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "output"
            with patch.dict("os.environ", {"EMIT_LEGACY_DASHBOARD": "0"}, clear=False):
                write_json_outputs(
                    _pm_schema_analyses(),
                    date(2026, 4, 8),
                    output_root=output_root,
                    portfolio_summary=_pm_schema_portfolio(),
                    portfolio_risk={"risk_grade": "C", "positions_by_weight": [{"ticker": "AAPL", "weight": 0.42}]},
                    decisions=_pm_schema_decisions(),
                )
            payload = json.loads((output_root / "data" / "dashboard_history.json").read_text(encoding="utf-8"))

        pm_view = payload["days"][0]["pm_view"]
        self.assertEqual(
            set(pm_view.keys()),
            {"as_of", "swap_candidates", "event_exposure_items", "today_priority_queue", "empty_states"},
        )
        self.assertEqual(pm_view["swap_candidates"][0]["held_ticker"], "AAPL")
        self.assertEqual(pm_view["swap_candidates"][0]["candidate_ticker"], "MSFT")
        self.assertEqual(pm_view["event_exposure_items"][0]["ticker"], "AAPL")
        self.assertTrue(all(item["destination"] == "portfolio" for item in pm_view["today_priority_queue"]))
        self.assertIn(
            ("swap_review", "MSFT"),
            {(item["priority_type"], item["related_ticker"]) for item in pm_view["today_priority_queue"]},
        )
        self.assertIn(
            ("event_review", None),
            {(item["priority_type"], item["related_ticker"]) for item in pm_view["today_priority_queue"]},
        )

        expected = load_snapshot_fixture(_FIXTURE_DIR / "pm_view.shape.json")
        self.assertEqual(normalize_json_shape(pm_view), expected)

    def test_sharded_index_pm_view_matches_populated_snapshot_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            output_root = Path(temp_dir) / "output"
            write_json_outputs(
                _pm_schema_analyses(),
                date(2026, 4, 8),
                output_root=output_root,
                portfolio_summary=_pm_schema_portfolio(),
                portfolio_risk={"risk_grade": "C", "positions_by_weight": [{"ticker": "AAPL", "weight": 0.42}]},
                decisions=_pm_schema_decisions(),
            )
            index_payload = json.loads((output_root / "data" / "index.json").read_text(encoding="utf-8"))

        self.assertIn("pm_view", index_payload)
        expected = load_snapshot_fixture(_FIXTURE_DIR / "pm_view.shape.json")
        self.assertEqual(normalize_json_shape(index_payload["pm_view"]), expected)

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
