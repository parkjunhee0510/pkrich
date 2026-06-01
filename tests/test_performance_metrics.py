from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.utils.performance_metrics import (
    build_performance_payloads,
    build_quality_reliability_loop_payload,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class PerformanceMetricsTests(unittest.TestCase):
    def test_build_quality_reliability_loop_payload_combines_existing_tracks(self) -> None:
        baseline = {
            "schema_version": 1,
            "as_of": "2026-05-21",
            "status": "ok",
            "latest_run_date": "2026-05-21",
            "json_health": {
                "status": "ok",
                "invalid_json_count": 0,
                "issues": [],
            },
            "cost": {
                "total_cost_usd": 1.25,
                "estimated_monthly_cost_usd": 27.5,
                "llm_calls": 220,
                "llm_calls_per_ticker": 9.565,
                "budget_guard_would_block_count": 4,
                "budget_guard_blocked_count": 0,
            },
            "quality": {
                "hallucination_ratio": 0.08,
                "validation_failure_rate": 0.02,
                "fact_warning_count": 3,
                "consistency_warning_count": 1,
            },
            "evidence": {
                "ticker_count": 4,
                "covered_ticker_count": 2,
                "coverage_ratio": 0.5,
                "searched_ticker_count": 2,
                "status_counts": {
                    "covered": 2,
                    "provider_unavailable": 1,
                    "no_evidence": 1,
                },
                "priority_ticker_count": 2,
                "priority_covered_ticker_count": 1,
                "priority_coverage_ratio": 0.5,
                "priority_status_counts": {
                    "covered": 1,
                    "provider_unavailable": 1,
                },
            },
            "p1_readiness": {
                "status": "ready",
                "tracks": {
                    "analysis_performance": {
                        "status": "ready",
                        "sample_count": 42,
                        "completed_return_window_count": 2,
                        "evaluated_signal_window_count": 4,
                        "populated_conviction_bucket_count": 3,
                        "factor_count": 8,
                        "action_change_coverage_ratio": 0.5,
                        "loop_readiness_status": "ready_for_quality_review",
                    },
                    "search_evidence_provider": {
                        "provider_issue_status": "provider_unavailable_seen",
                        "operational_issue_count": 1,
                    },
                    "budget_guard": {
                        "status": "report_ready",
                        "mode": "shadow",
                        "would_block_count": 4,
                        "blocked_count": 0,
                    },
                    "output_schema": {
                        "status": "ready",
                        "invalid_json_count": 0,
                    },
                },
            },
        }
        trends = {
            "schema_version": 1,
            "as_of": "2026-05-21",
            "runs": [
                {
                    "run_date": "2026-05-20",
                    "success": True,
                    "total_cost_usd": 1.0,
                    "llm_calls": 200,
                    "hallucination_ratio": 0.1,
                    "validation_failure_count": 2,
                    "deep_selected_count": 5,
                    "budget_guard_would_block_count": 3,
                },
                {
                    "run_date": "2026-05-21",
                    "success": True,
                    "total_cost_usd": 1.25,
                    "llm_calls": 220,
                    "hallucination_ratio": 0.08,
                    "validation_failure_count": 1,
                    "deep_selected_count": 6,
                    "budget_guard_would_block_count": 4,
                },
            ],
        }

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends=trends)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["as_of"], "2026-05-21")
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["summary"]["decision_quality_status"], "ok")
        self.assertEqual(payload["summary"]["artifact_reliability_status"], "ok")
        self.assertEqual(payload["summary"]["evidence_status"], "partial")
        self.assertEqual(payload["summary"]["cost_status"], "reported")
        self.assertEqual(payload["decision_quality"]["sample_count"], 42)
        self.assertEqual(payload["artifact_reliability"]["invalid_json_count"], 0)
        self.assertEqual(payload["evidence_quality"]["coverage_ratio"], 0.5)
        self.assertEqual(payload["cost_and_runtime"]["total_cost_usd"], 1.25)
        self.assertEqual(payload["cost_and_runtime"]["cost_policy"], "report_only")
        self.assertEqual(payload["trend_inputs"]["run_count"], 2)
        self.assertIn("provider_issue_seen", payload["warnings"])

    def test_build_quality_reliability_loop_payload_marks_invalid_json_failed(self) -> None:
        baseline = {
            "schema_version": 1,
            "as_of": "2026-05-21",
            "status": "degraded",
            "json_health": {
                "status": "invalid_json",
                "invalid_json_count": 1,
                "issues": [
                    {
                        "path": "broken.json",
                        "error": "Expecting value",
                    }
                ],
            },
            "cost": {},
            "evidence": {},
            "p1_readiness": {
                "tracks": {
                    "analysis_performance": {
                        "status": "insufficient_data",
                        "loop_readiness_status": "needs_samples",
                    },
                    "search_evidence_provider": {},
                    "budget_guard": {},
                    "output_schema": {
                        "status": "needs_attention",
                        "invalid_json_count": 1,
                    },
                },
            },
        }

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends={"runs": []})

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["summary"]["artifact_reliability_status"], "failed")
        self.assertEqual(payload["summary"]["decision_quality_status"], "insufficient_data")
        self.assertEqual(payload["summary"]["cost_status"], "missing")
        self.assertIn("invalid_json_detected", payload["warnings"])

    def test_quality_reliability_loop_warns_on_priority_evidence_gaps(self) -> None:
        baseline = {
            "schema_version": 1,
            "as_of": "2026-05-07",
            "status": "ok",
            "latest_run_date": "2026-05-07",
            "quality": {
                "validated_ticker_count": 10,
                "validation_failure_count": 0,
                "validation_failure_rate": 0.0,
                "hallucination_warning_count": 0,
                "hallucination_ratio": 0.0,
                "fact_warning_count": 0,
                "consistency_warning_count": 0,
            },
            "evidence": {
                "ticker_count": 2,
                "covered_ticker_count": 0,
                "coverage_ratio": 0.0,
                "searched_ticker_count": 0,
                "status_counts": {"not_refreshed": 1, "provider_error": 1},
                "priority_ticker_count": 2,
                "priority_covered_ticker_count": 0,
                "priority_coverage_ratio": 0.0,
                "priority_status_counts": {"not_refreshed": 1, "provider_error": 1},
                "priority_refresh_reasons": {"stale_cache": 1},
                "priority_refresh_candidate_count": 1,
                "priority_provider_error_count": 1,
                "priority_not_refreshed_count": 1,
                "priority_no_evidence_count": 0,
            },
            "json_health": {
                "status": "ok",
                "invalid_json_count": 0,
                "issues": [],
                "output_schema_status": "ok",
            },
            "cost": {},
            "p1_readiness": {
                "tracks": {
                    "search_evidence_provider": {
                        "provider_issue_status": "provider_error_seen",
                        "operational_issue_count": 1,
                    },
                    "budget_guard": {
                        "status": "enforce_active",
                        "mode": "shadow",
                        "blocked_count": 1,
                    },
                    "analysis_performance": {
                        "status": "ready",
                        "sample_count": 5,
                        "completed_return_window_count": 1,
                        "evaluated_signal_window_count": 1,
                        "populated_conviction_bucket_count": 1,
                        "factor_count": 3,
                        "action_change_coverage_ratio": 1.0,
                        "loop_readiness_status": "ready_for_quality_review",
                    },
                    "output_schema": {"status": "ready", "invalid_json_count": 0},
                }
            },
        }

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends={"runs": []})

        self.assertIn("priority_evidence_zero_coverage", payload["warnings"])
        self.assertIn("priority_evidence_not_refreshed", payload["warnings"])
        self.assertIn("priority_evidence_provider_error", payload["warnings"])
        self.assertIn("priority_evidence_stale_cache", payload["warnings"])
        self.assertIn("provider_issue_seen", payload["warnings"])
        self.assertIn("budget_guard_enforced_block_seen", payload["warnings"])
        self.assertIn("cost_telemetry_missing", payload["warnings"])
        self.assertEqual(payload["evidence_quality"]["priority_refresh_candidate_count"], 1)
        self.assertEqual(payload["evidence_quality"]["priority_provider_error_count"], 1)
        self.assertEqual(payload["evidence_quality"]["priority_not_refreshed_count"], 1)

    def test_quality_reliability_loop_clamps_malformed_priority_evidence(self) -> None:
        baseline = {
            "schema_version": 1,
            "as_of": "2026-05-07",
            "status": "ok",
            "latest_run_date": "2026-05-07",
            "quality": {
                "hallucination_ratio": 0.0,
                "validation_failure_rate": 0.0,
                "fact_warning_count": 0,
                "consistency_warning_count": 0,
            },
            "evidence": {
                "ticker_count": 2,
                "covered_ticker_count": 1,
                "coverage_ratio": 0.5,
                "searched_ticker_count": 1,
                "status_counts": {"covered": 1},
                "priority_ticker_count": -2,
                "priority_covered_ticker_count": "n/a",
                "priority_coverage_ratio": 0.0,
                "priority_status_counts": {
                    "provider_error": -1,
                    "not_refreshed": -2,
                    "no_evidence": -3,
                },
                "priority_refresh_reasons": {"stale_cache": -3},
                "priority_refresh_candidate_count": -1,
                "priority_provider_error_count": -1,
                "priority_not_refreshed_count": -2,
                "priority_no_evidence_count": -3,
            },
            "json_health": {
                "status": "ok",
                "invalid_json_count": 0,
                "issues": [],
            },
            "cost": {
                "total_cost_usd": 0.1,
                "estimated_monthly_cost_usd": 1.0,
                "llm_calls": 3,
                "llm_calls_per_ticker": 1.5,
                "budget_guard_would_block_count": 0,
                "budget_guard_blocked_count": 0,
            },
            "p1_readiness": {
                "tracks": {
                    "search_evidence_provider": {
                        "provider_issue_status": "clean",
                        "operational_issue_count": 0,
                    },
                    "budget_guard": {
                        "status": "shadow_observing",
                        "mode": "shadow",
                        "blocked_count": 0,
                    },
                    "analysis_performance": {
                        "status": "ready",
                        "sample_count": 5,
                        "completed_return_window_count": 1,
                        "evaluated_signal_window_count": 1,
                        "populated_conviction_bucket_count": 1,
                        "factor_count": 3,
                        "action_change_coverage_ratio": 1.0,
                        "loop_readiness_status": "ready_for_quality_review",
                    },
                    "output_schema": {"status": "ready", "invalid_json_count": 0},
                }
            },
        }

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends={"runs": []})

        self.assertEqual(payload["evidence_quality"]["priority_ticker_count"], 0)
        self.assertEqual(payload["evidence_quality"]["priority_covered_ticker_count"], 0)
        self.assertEqual(
            payload["evidence_quality"]["priority_status_counts"],
            {"provider_error": 0, "not_refreshed": 0, "no_evidence": 0},
        )
        self.assertEqual(
            payload["evidence_quality"]["priority_refresh_reasons"],
            {"stale_cache": 0},
        )
        self.assertEqual(payload["evidence_quality"]["priority_refresh_candidate_count"], 0)
        self.assertEqual(payload["evidence_quality"]["priority_provider_error_count"], 0)
        self.assertEqual(payload["evidence_quality"]["priority_not_refreshed_count"], 0)
        self.assertEqual(payload["evidence_quality"]["priority_no_evidence_count"], 0)
        self.assertFalse(
            any(
                warning.startswith("priority_evidence_")
                for warning in payload["warnings"]
            )
        )

    def test_build_quality_reliability_loop_payload_treats_normalized_empty_inputs_as_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends=trends)

        self.assertEqual(
            payload["summary"]["decision_quality_status"],
            "insufficient_data",
        )
        self.assertEqual(payload["summary"]["cost_status"], "missing")
        self.assertEqual(payload["summary"]["evidence_status"], "insufficient_data")
        self.assertIn("cost_telemetry_missing", payload["warnings"])
        self.assertIn("decision_quality_insufficient_samples", payload["warnings"])
        self.assertIn("evidence_quality_insufficient_data", payload["warnings"])

    def test_build_quality_reliability_loop_payload_defaults_malformed_scalars(
        self,
    ) -> None:
        baseline = {
            "schema_version": 1,
            "as_of": "2026-05-21",
            "json_health": {
                "status": "ok",
                "invalid_json_count": "n/a",
                "issues": [],
            },
            "latest_run_date": "",
            "cost": {
                "total_cost_usd": "n/a",
                "estimated_monthly_cost_usd": "n/a",
                "llm_calls": "n/a",
                "llm_calls_per_ticker": "n/a",
                "budget_guard_would_block_count": "n/a",
                "budget_guard_blocked_count": "n/a",
            },
            "quality": {
                "hallucination_ratio": "n/a",
                "validation_failure_rate": "n/a",
                "fact_warning_count": "n/a",
                "consistency_warning_count": "n/a",
            },
            "evidence": {
                "provider": "",
                "ticker_count": "n/a",
                "covered_ticker_count": "n/a",
                "coverage_ratio": "n/a",
                "candidate_ticker_count": "n/a",
                "searched_ticker_count": "n/a",
                "status_counts": {},
                "priority_ticker_count": "n/a",
                "priority_covered_ticker_count": "n/a",
                "priority_coverage_ratio": "n/a",
                "priority_status_counts": {},
            },
            "p1_readiness": {
                "tracks": {
                    "analysis_performance": {
                        "sample_count": "n/a",
                        "completed_return_window_count": "n/a",
                        "evaluated_signal_window_count": "n/a",
                        "populated_conviction_bucket_count": "n/a",
                        "factor_count": "n/a",
                        "action_change_coverage_ratio": "n/a",
                        "loop_readiness_status": "needs_samples",
                    },
                    "search_evidence_provider": {
                        "provider_issue_status": "clean",
                        "operational_issue_count": "n/a",
                    },
                    "budget_guard": {
                        "blocked_count": "n/a",
                    },
                    "output_schema": {
                        "status": "ready",
                        "invalid_json_count": "n/a",
                    },
                },
            },
        }

        payload = build_quality_reliability_loop_payload(
            baseline=baseline,
            trends={"runs": []},
        )

        self.assertEqual(payload["summary"]["decision_quality_status"], "insufficient_data")
        self.assertEqual(payload["summary"]["artifact_reliability_status"], "ok")
        self.assertEqual(payload["summary"]["cost_status"], "missing")
        self.assertEqual(payload["summary"]["evidence_status"], "insufficient_data")
        self.assertEqual(payload["decision_quality"]["sample_count"], 0)
        self.assertEqual(payload["artifact_reliability"]["invalid_json_count"], 0)
        self.assertEqual(payload["evidence_quality"]["coverage_ratio"], 0.0)
        self.assertEqual(payload["cost_and_runtime"]["total_cost_usd"], 0.0)
        self.assertEqual(payload["cost_and_runtime"]["llm_calls"], 0)

    def test_build_performance_payloads_defaults_malformed_source_scalars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-21",
                        "total_cost_usd": "n/a",
                        "profiles": {
                            "economy": {"calls": "n/a"},
                        },
                        "budget_guard": {
                            "would_block_count": "n/a",
                        },
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-21",
                            "success": True,
                            "total_cost_usd": "n/a",
                            "profiles": {
                                "economy": {"calls": "n/a"},
                            },
                            "budget_guard": {
                                "would_block_count": "n/a",
                            },
                        }
                    ],
                },
            )
            _write_json(
                data / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-21",
                        "validated_ticker_count": "n/a",
                        "validation_failure_count": "n/a",
                        "hallucination_warning_count": "n/a",
                        "hallucination_ratio": "n/a",
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-21",
                            "validation_failure_count": "n/a",
                            "hallucination_ratio": "n/a",
                        }
                    ],
                },
            )
            _write_json(
                data / "search_evidence.json",
                {
                    "schema_version": 1,
                    "provider": "cache",
                    "by_ticker": {
                        "AAPL": {
                            "evidence_count": "n/a",
                            "coverage_score": "n/a",
                            "freshness_score": "n/a",
                            "evidence_status": "no_evidence",
                        }
                    },
                    "run_summary": {
                        "candidate_ticker_count": "n/a",
                        "searched_ticker_count": "n/a",
                    },
                },
            )

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends=trends)

        self.assertEqual(baseline["cost"]["total_cost_usd"], 0.0)
        self.assertEqual(baseline["cost"]["llm_calls"], 0)
        self.assertEqual(baseline["cost"]["budget_guard_would_block_count"], 0)
        self.assertEqual(baseline["quality"]["validation_failure_count"], 0)
        self.assertEqual(baseline["quality"]["hallucination_ratio"], 0.0)
        self.assertEqual(baseline["evidence"]["covered_ticker_count"], 0)
        self.assertEqual(baseline["evidence"]["candidate_ticker_count"], 0)
        self.assertEqual(trends["runs"][0]["llm_calls"], 0)
        self.assertEqual(trends["runs"][0]["total_cost_usd"], 0.0)
        self.assertEqual(payload["cost_and_runtime"]["cost_policy"], "report_only")

    def test_build_performance_payloads_clamps_negative_priority_evidence_summary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {"run_date": "2026-05-21"},
                    "runs": [],
                },
            )
            _write_json(
                data / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {"run_date": "2026-05-21"},
                    "runs": [],
                },
            )
            _write_json(
                data / "search_evidence.json",
                {
                    "schema_version": 1,
                    "provider": "cache",
                    "by_ticker": {
                        "AAPL": {
                            "evidence_count": 0,
                            "coverage_score": 0.0,
                            "freshness_score": 0.0,
                            "evidence_status": "provider_error",
                            "priority_for_refresh": True,
                        }
                    },
                    "run_summary": {
                        "candidate_ticker_count": 1,
                        "provider_candidate_count": 1,
                        "priority_tickers": ["AAPL"],
                        "priority_ticker_count": -2,
                        "priority_status_counts": {
                            "provider_error": -1,
                            "not_refreshed": -2,
                            "no_evidence": -3,
                        },
                        "priority_refresh_reasons": {
                            "router_selected": -4,
                            "stale_cache": -5,
                        },
                        "priority_refresh_candidate_count": -6,
                    },
                },
            )

            baseline, _trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        self.assertEqual(
            baseline["evidence"]["priority_status_counts"],
            {"provider_error": 0, "not_refreshed": 0, "no_evidence": 0},
        )
        self.assertEqual(
            baseline["evidence"]["priority_refresh_reasons"],
            {"router_selected": 0, "stale_cache": 0},
        )
        self.assertEqual(baseline["evidence"]["priority_refresh_candidate_count"], 0)
        self.assertEqual(baseline["evidence"]["priority_provider_error_count"], 0)
        self.assertEqual(baseline["evidence"]["priority_not_refreshed_count"], 0)
        self.assertEqual(baseline["evidence"]["priority_no_evidence_count"], 0)
        provider_track = baseline["p1_readiness"]["tracks"]["search_evidence_provider"]
        self.assertEqual(provider_track["priority_ticker_count"], 0)
        self.assertEqual(provider_track["priority_refresh_candidate_ratio"], 0.0)

    def test_build_performance_payloads_derives_not_refreshed_from_priority_reasons(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "search_evidence.json",
                {
                    "schema_version": 1,
                    "provider": "cache",
                    "by_ticker": {
                        "CAT": {
                            "evidence_count": 0,
                            "coverage_score": 0.0,
                            "freshness_score": 0.0,
                            "evidence_status": "no_evidence",
                            "priority_for_refresh": True,
                        },
                        "AMD": {
                            "evidence_count": 0,
                            "coverage_score": 0.0,
                            "freshness_score": 0.0,
                            "evidence_status": "no_evidence",
                            "priority_for_refresh": True,
                        },
                    },
                    "run_summary": {
                        "candidate_ticker_count": 2,
                        "searched_ticker_count": 0,
                        "priority_tickers": ["CAT", "AMD"],
                        "priority_ticker_count": 2,
                        "priority_status_counts": {"no_evidence": 2},
                        "priority_refresh_reasons": {
                            "router_selected": 2,
                            "not_refreshed": 2,
                        },
                        "priority_refresh_candidate_count": 0,
                    },
                },
            )

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends=trends)

        self.assertEqual(baseline["evidence"]["priority_no_evidence_count"], 2)
        self.assertEqual(baseline["evidence"]["priority_not_refreshed_count"], 2)
        self.assertEqual(payload["evidence_quality"]["priority_not_refreshed_count"], 2)
        self.assertIn("priority_evidence_not_refreshed", payload["warnings"])

    def test_build_performance_payloads_defaults_non_finite_source_scalars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "total_cost_usd": "NaN",
                        "profiles": {
                            "economy": {"calls": "Infinity"},
                        },
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-21",
                            "success": True,
                            "total_cost_usd": "Infinity",
                            "profiles": {
                                "economy": {"calls": "NaN"},
                            },
                        }
                    ],
                },
            )
            _write_json(
                data / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "hallucination_ratio": "NaN",
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-21",
                            "hallucination_ratio": "Infinity",
                        }
                    ],
                },
            )
            _write_json(
                data / "search_evidence.json",
                {
                    "schema_version": 1,
                    "provider": "",
                    "by_ticker": {
                        "AAPL": {
                            "evidence_count": 0,
                            "coverage_score": "NaN",
                            "freshness_score": "Infinity",
                        }
                    },
                    "run_summary": {},
                },
            )

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends=trends)

        self.assertEqual(baseline["cost"]["total_cost_usd"], 0.0)
        self.assertEqual(baseline["quality"]["hallucination_ratio"], 0.0)
        self.assertEqual(baseline["evidence"]["average_coverage_score"], 0.0)
        self.assertEqual(baseline["evidence"]["average_freshness_score"], 0.0)
        self.assertEqual(trends["runs"][0]["total_cost_usd"], 0.0)
        self.assertEqual(trends["runs"][0]["hallucination_ratio"], 0.0)
        self.assertEqual(payload["cost_and_runtime"]["total_cost_usd"], 0.0)
        self.assertEqual(payload["decision_quality"]["hallucination_ratio"], 0.0)
        self.assertEqual(payload["summary"]["cost_status"], "missing")
        json.dumps(baseline, allow_nan=False)
        json.dumps(trends, allow_nan=False)
        json.dumps(payload, allow_nan=False)

    def test_build_performance_payloads_defaults_unquoted_infinity_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            data.mkdir(parents=True)
            (data / "cost_log.json").write_text(
                """
{
  "schema_version": 1,
  "latest": {
    "total_cost_usd": 0.0,
    "profiles": {
      "economy": {"calls": Infinity}
    },
    "routing": {
      "eligible_count": Infinity,
      "selected_count": Infinity
    },
    "budget_guard": {
      "would_block_count": Infinity,
      "blocked_count": Infinity
    }
  },
  "runs": [
    {
      "run_date": "2026-05-21",
      "success": true,
      "profiles": {
        "economy": {"calls": Infinity}
      },
      "routing": {
        "selected_count": Infinity
      },
      "budget_guard": {
        "would_block_count": Infinity
      }
    }
  ]
}
""",
                encoding="utf-8",
            )
            (data / "search_evidence.json").write_text(
                """
{
  "schema_version": 1,
  "provider": "cache",
  "by_ticker": {
    "AAPL": {
      "evidence_count": Infinity,
      "coverage_score": 0.5,
      "freshness_score": 0.5,
      "cache_age_hours": Infinity,
      "evidence_status": "covered",
      "priority_for_refresh": true
    }
  },
  "run_summary": {
    "candidate_ticker_count": Infinity,
    "searched_ticker_count": Infinity,
    "provider_candidate_count": Infinity,
    "priority_tickers": ["AAPL"],
    "priority_ticker_count": Infinity,
    "status_counts": {
      "covered": Infinity
    }
  }
}
""",
                encoding="utf-8",
            )

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        payload = build_quality_reliability_loop_payload(baseline=baseline, trends=trends)

        self.assertEqual(baseline["cost"]["llm_calls"], 0)
        self.assertEqual(baseline["cost"]["ticker_count_for_rate"], 0)
        self.assertEqual(baseline["cost"]["deep_selected_count"], 0)
        self.assertEqual(baseline["cost"]["budget_guard_would_block_count"], 0)
        self.assertEqual(baseline["cost"]["budget_guard_blocked_count"], 0)
        self.assertEqual(baseline["evidence"]["covered_ticker_count"], 0)
        self.assertEqual(baseline["evidence"]["candidate_ticker_count"], 0)
        self.assertEqual(baseline["evidence"]["searched_ticker_count"], 0)
        self.assertEqual(baseline["evidence"]["provider_candidate_count"], 0)
        self.assertEqual(baseline["evidence"]["status_counts"], {"covered": 0})
        self.assertEqual(trends["runs"][0]["llm_calls"], 0)
        self.assertEqual(trends["runs"][0]["deep_selected_count"], 0)
        self.assertEqual(trends["runs"][0]["budget_guard_would_block_count"], 0)
        json.dumps(baseline, allow_nan=False)
        json.dumps(trends, allow_nan=False)
        json.dumps(payload, allow_nan=False)

    def test_build_performance_payloads_handles_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        self.assertEqual(baseline["schema_version"], 1)
        self.assertEqual(baseline["status"], "insufficient_data")
        self.assertEqual(baseline["json_health"]["invalid_json_count"], 0)
        self.assertEqual(trends["runs"], [])

    def test_build_performance_payloads_treats_null_run_lists_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {"run_date": "2026-05-21", "total_cost_usd": 0.25},
                    "runs": None,
                },
            )
            _write_json(
                data / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {"run_date": "2026-05-21", "success": True},
                    "runs": None,
                },
            )

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        self.assertEqual(baseline["status"], "ok")
        self.assertEqual(baseline["latest_run_date"], "2026-05-21")
        self.assertEqual(trends["runs"], [])

    def test_build_performance_payloads_combines_cost_quality_evidence_and_signal_quality(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "success": True,
                        "total_cost_usd": 0.43,
                        "profiles": {
                            "economy": {"calls": 145, "cost_usd": 0.19},
                            "deep": {"calls": 19, "cost_usd": 0.12},
                            "standard": {"calls": 15, "cost_usd": 0.12},
                        },
                        "routing": {
                            "eligible_count": 23,
                            "selected_count": 5,
                            "conflicted_count": 3,
                        },
                        "budget_guard": {
                            "mode": "shadow",
                            "decision_counts": {"allow": 1, "would_block": 6},
                            "guarded_paths": {
                                "committee_deep": "would_block",
                                "ensemble_deep": "would_block",
                                "search_evidence": "allow",
                            },
                            "profile_counts": {"deep": 6, "standard": 1},
                            "would_block_count": 6,
                            "blocked_count": 0,
                            "total_estimated_incremental_cost_usd": 0.3784,
                        },
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-07",
                            "success": True,
                            "total_cost_usd": 0.43,
                            "profiles": {
                                "economy": {"calls": 145},
                                "deep": {"calls": 19},
                                "standard": {"calls": 15},
                            },
                            "routing": {
                                "eligible_count": 23,
                                "selected_count": 5,
                                "conflicted_count": 3,
                            },
                            "budget_guard": {"would_block_count": 6, "blocked_count": 0},
                        }
                    ],
                },
            )
            _write_json(
                data / "analysis_quality.json",
                {
                    "schema_version": 1,
                    "latest": {
                        "run_date": "2026-05-07",
                        "validated_ticker_count": 283,
                        "validation_failure_count": 17,
                        "hallucination_warning_count": 35,
                        "hallucination_ratio": 0.1237,
                    },
                    "runs": [
                        {
                            "run_date": "2026-05-07",
                            "validated_ticker_count": 283,
                            "validation_failure_count": 17,
                            "hallucination_warning_count": 35,
                            "hallucination_ratio": 0.1237,
                        }
                    ],
                },
            )
            _write_json(
                data / "search_evidence.json",
                {
                    "schema_version": 1,
                    "provider": "cache",
                    "by_ticker": {
                        "AAPL": {
                            "evidence_count": 2,
                            "coverage_score": 0.8,
                            "freshness_score": 0.9,
                            "evidence_status": "covered",
                            "priority_for_refresh": True,
                            "cache_age_hours": 0,
                        },
                        "AMD": {
                            "evidence_count": 0,
                            "coverage_score": 0.0,
                            "freshness_score": 0.0,
                            "evidence_status": "provider_unavailable",
                            "priority_for_refresh": True,
                            "cache_age_hours": 0,
                        },
                        "COHR": {
                            "evidence_count": 1,
                            "coverage_score": 0.4,
                            "freshness_score": 0.6,
                            "evidence_status": "covered",
                            "priority_for_refresh": False,
                            "cache_source_date": "2026-05-06",
                            "cache_age_hours": 24,
                        },
                    },
                    "run_summary": {
                        "candidate_ticker_count": 3,
                        "searched_ticker_count": 2,
                        "cache_hit_count": 2,
                        "stale_cache_hit_count": 1,
                        "cache_ttl_hours": 48,
                        "priority_tickers": ["AAPL", "AMD"],
                        "priority_ticker_count": 2,
                        "provider_candidate_count": 2,
                        "provider_call_count": 0,
                        "provider_error_count": 0,
                        "cache_error_count": 0,
                        "skipped_ticker_count": 1,
                        "priority_refresh_reasons": {
                            "router_selected": 2,
                            "stale_cache": 1,
                            "no_evidence": 1,
                        },
                        "priority_status_counts": {
                            "covered": 1,
                            "provider_unavailable": 1,
                        },
                        "priority_refresh_candidate_count": 2,
                        "status_counts": {
                            "covered": 2,
                            "provider_unavailable": 1,
                        },
                    },
                },
            )
            _write_json(
                data / "signal_quality.json",
                {
                    "schema_version": 1,
                    "kelly": {"status": "ok"},
                    "turnover": {"status": "ok", "avg_turnover": 0.047},
                },
            )
            _write_json(
                data / "analysis_performance.json",
                {
                    "schema_version": 1,
                    "as_of": "2026-05-07",
                    "summary": {
                        "sample_count": 42,
                        "decision_count": 4,
                        "completed_return_windows": ["1d", "5d"],
                        "mode": "shadow_observational",
                    },
                    "signal_performance": {
                        "buy": {
                            "1d": {"completed_count": 3},
                            "5d": {"completed_count": 2},
                        },
                        "watch": {
                            "1d": {"completed_count": 4},
                            "5d": {"completed_count": 0},
                        },
                    },
                    "conviction_calibration": {
                        "status": "observational",
                        "buckets": {
                            "35_50": {"sample_count": 12},
                            "50_65": {"sample_count": 0},
                        },
                    },
                    "regime_performance": {
                        "risk_on": {},
                        "risk_off": {},
                    },
                    "factor_attribution": {
                        "status": "observed_association",
                        "missing_factor_sample_count": 5,
                        "factors": {
                            "momentum": {"sample_count": 20},
                            "valuation": {"sample_count": 18},
                        },
                    },
                    "action_change_reasons": [
                        {"ticker": "AAPL"},
                        {"ticker": "AMD"},
                    ],
                },
            )

            baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        self.assertEqual(baseline["status"], "ok")
        self.assertEqual(baseline["latest_run_date"], "2026-05-07")
        self.assertEqual(baseline["cost"]["total_cost_usd"], 0.43)
        self.assertEqual(baseline["cost"]["llm_calls"], 179)
        self.assertEqual(baseline["cost"]["llm_calls_per_ticker"], 7.783)
        self.assertEqual(baseline["quality"]["hallucination_ratio"], 0.1237)
        self.assertEqual(baseline["evidence"]["ticker_count"], 3)
        self.assertEqual(baseline["evidence"]["covered_ticker_count"], 2)
        self.assertEqual(baseline["evidence"]["coverage_ratio"], 0.6667)
        self.assertEqual(baseline["evidence"]["cache_ttl_hours"], 48)
        self.assertEqual(baseline["evidence"]["cache_hit_count"], 2)
        self.assertEqual(baseline["evidence"]["stale_cache_hit_count"], 1)
        self.assertEqual(baseline["evidence"]["cache_hit_ratio"], 0.6667)
        self.assertEqual(baseline["evidence"]["stale_cache_hit_ratio"], 0.5)
        self.assertEqual(baseline["evidence"]["average_cache_age_hours"], 12.0)
        self.assertEqual(baseline["evidence"]["max_cache_age_hours"], 24)
        self.assertEqual(baseline["evidence"]["priority_ticker_count"], 2)
        self.assertEqual(baseline["evidence"]["priority_covered_ticker_count"], 1)
        self.assertEqual(baseline["evidence"]["priority_coverage_ratio"], 0.5)
        self.assertEqual(
            baseline["evidence"]["priority_status_counts"],
            {"covered": 1, "provider_unavailable": 1},
        )
        self.assertEqual(
            baseline["evidence"]["priority_refresh_reasons"],
            {
                "router_selected": 2,
                "stale_cache": 1,
                "no_evidence": 1,
            },
        )
        self.assertEqual(baseline["evidence"]["priority_refresh_candidate_count"], 2)
        self.assertEqual(baseline["evidence"]["priority_provider_error_count"], 0)
        self.assertEqual(baseline["evidence"]["priority_not_refreshed_count"], 0)
        self.assertEqual(baseline["evidence"]["priority_no_evidence_count"], 0)
        self.assertEqual(
            baseline["evidence"]["status_counts"],
            {"covered": 2, "provider_unavailable": 1},
        )
        self.assertEqual(baseline["evidence"]["provider_candidate_count"], 2)
        self.assertEqual(baseline["signals"]["turnover_status"], "ok")
        self.assertEqual(baseline["p1_readiness"]["status"], "ready")
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"]["status"],
            "ready_for_limited_provider_validation",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"][
                "cap_review_status"
            ],
            "priority_queued_within_cap",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"][
                "priority_refresh_candidate_ratio"
            ],
            1.0,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"][
                "provider_issue_status"
            ],
            "provider_unavailable_seen",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"][
                "stale_cache_reuse_status"
            ],
            "stale_cache_reused",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"][
                "provider_call_count"
            ],
            0,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["search_evidence_provider"][
                "skipped_ticker_count"
            ],
            1,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["budget_guard"]["status"],
            "report_ready",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["budget_guard"]["decision_counts"],
            {"allow": 1, "would_block": 6},
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["budget_guard"][
                "guarded_path_status_counts"
            ],
            {"allow": 1, "would_block": 2},
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["budget_guard"]["would_block_path_count"],
            2,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["budget_guard"]["enforce_review_status"],
            "report_only_review_required",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"]["sample_count"],
            42,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"][
                "loop_readiness_status"
            ],
            "ready_for_quality_review",
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"][
                "completed_return_window_count"
            ],
            2,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"][
                "evaluated_signal_window_count"
            ],
            3,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"][
                "populated_conviction_bucket_count"
            ],
            1,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"]["factor_count"],
            2,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["analysis_performance"][
                "action_change_coverage_ratio"
            ],
            0.5,
        )
        self.assertEqual(
            baseline["p1_readiness"]["tracks"]["output_schema"]["invalid_json_count"],
            0,
        )
        self.assertEqual(trends["runs"][0]["run_date"], "2026-05-07")
        self.assertEqual(trends["runs"][0]["llm_calls"], 179)

    def test_build_performance_payloads_counts_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            data.mkdir(parents=True)
            (data / "broken.json").write_text('{"schema_version": ', encoding="utf-8")

            baseline, _trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        self.assertEqual(baseline["json_health"]["invalid_json_count"], 1)
        self.assertEqual(baseline["json_health"]["issues"][0]["path"], "broken.json")

    def test_build_performance_payloads_sorts_trend_runs_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "output"
            data = root / "data"
            _write_json(
                data / "cost_log.json",
                {
                    "schema_version": 1,
                    "latest": {"run_date": "2026-05-07"},
                    "runs": [
                        {"run_date": "2026-05-07", "success": True},
                        {"run_date": "2026-05-06", "success": True},
                    ],
                },
            )

            _baseline, trends = build_performance_payloads(
                output_root=root,
                logs_root=Path(temp_dir) / "logs" / "pipeline",
            )

        self.assertEqual(
            [run["run_date"] for run in trends["runs"]],
            ["2026-05-06", "2026-05-07"],
        )


if __name__ == "__main__":
    unittest.main()
