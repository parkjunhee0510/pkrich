import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path

from src.output.health_check import check_output_health


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _valid_search_evidence_payload() -> dict:
    return {
        "schema_version": 1,
        "date": "2026-05-07",
        "provider": "cache",
        "items": [],
        "by_ticker": {
            "AAPL": {
                "evidence_count": 1,
                "evidence_status": "covered",
                "provider_status": "cache_hit",
                "priority_for_refresh": True,
                "priority_refresh_reasons": ["router_selected", "stale_cache"],
                "cache_source_date": "2026-05-07",
                "cache_age_hours": 2,
                "coverage_score": 1.0,
                "freshness_score": 0.9,
            },
            "MSFT": {
                "evidence_count": 1,
                "evidence_status": "covered",
                "provider_status": "cache_hit",
                "priority_for_refresh": False,
                "priority_refresh_reasons": [],
                "cache_source_date": "2026-05-07",
                "cache_age_hours": 3,
                "coverage_score": 1.0,
                "freshness_score": 0.8,
            },
        },
        "run_summary": {
            "candidate_ticker_count": 2,
            "searched_ticker_count": 0,
            "cache_hit_count": 2,
            "cache_error_count": 0,
            "cache_ttl_hours": 24,
            "stale_cache_hit_count": 0,
            "status_counts": {"covered": 2},
            "priority_tickers": ["AAPL"],
            "priority_ticker_count": 1,
            "priority_refresh_reasons": {"router_selected": 1, "stale_cache": 1},
            "priority_status_counts": {"covered": 1},
            "priority_refresh_candidate_count": 0,
            "provider_candidate_count": 0,
            "provider_call_count": 0,
            "provider_error_count": 0,
            "skipped_ticker_count": 0,
        },
    }


def _valid_search_audit_payload() -> dict:
    return {
        "schema_version": 1,
        "date": "2026-05-07",
        "generated_at": "2026-05-07T00:00:00+00:00",
        "source": "search_evidence",
        "tickers": [
            {
                "ticker": "AAPL",
                "verdict": "warn",
                "checked_claims": 1,
                "supported_claims": 0,
                "conflicting_claims": 0,
                "missing_evidence_claims": 1,
                "insufficient_evidence_claims": 0,
                "issues": [
                    {
                        "claim": "Revenue grew 10%.",
                        "field": "summary",
                        "status": "missing_evidence",
                        "source_url": "",
                        "source_domain": "",
                        "source_title": "",
                        "match_score": 0.0,
                    }
                ],
            }
        ],
        "run_summary": {
            "ticker_count": 1,
            "checked_claims": 1,
            "supported_claims": 0,
            "conflicting_claims": 0,
            "missing_evidence_claims": 1,
            "insufficient_evidence_claims": 0,
            "issue_count": 1,
        },
    }


def _valid_backtest_payload() -> dict:
    return {
        "schema_version": 1,
        "status": "ok",
        "strategy": "Evaluate bull/bear signals separately on a 20-trading-day horizon.",
        "signals": 2,
        "pending_signals": 1,
        "first_eval_date": "2026-05-08",
        "win_rate": "50.0%",
        "avg_return": "+1.00%",
        "cumulative_return": "+2.00%",
        "best_return": "+3.00%",
        "worst_return": "-1.00%",
        "bull": {
            "direction": "bull",
            "signals": 1,
            "win_rate": "100.0%",
            "avg_return": "+3.00%",
            "cumulative_return": "+3.00%",
            "best_return": "+3.00%",
            "worst_return": "+3.00%",
        },
        "bear": {
            "direction": "bear",
            "signals": 1,
            "win_rate": "0.0%",
            "avg_return": "-1.00%",
            "cumulative_return": "-1.00%",
            "best_return": "-1.00%",
            "worst_return": "-1.00%",
        },
        "equity_curve": [
            {
                "date": "2026-04-01",
                "ticker": "AAPL",
                "signal_direction": "bull",
                "strategy_return": "+3.00%",
                "equity_multiple": 1.03,
                "cumulative_return": "+3.00%",
            }
        ],
        "ticker_rows": [
            {
                "ticker": "AAPL",
                "signals": 1,
                "avg_return": "+3.00%",
                "win_rate": "100.0%",
                "bull_signals": 1,
                "bear_signals": 0,
                "best_return": "+3.00%",
                "worst_return": "+3.00%",
            }
        ],
    }


def _valid_monthly_payload() -> dict:
    return {
        "schema_version": 1,
        "month": "2026-05",
        "status": "ok",
        "trading_days": 3,
        "start_date": "2026-05-01",
        "end_date": "2026-05-06",
        "top_tickers": [
            {
                "ticker": "AAPL",
                "avg_daily_change": "+1.23%",
            }
        ],
        "top_sectors": [
            {
                "sector": "Technology",
                "avg_daily_change": "+0.98%",
            }
        ],
    }


def _valid_routing_outcome_payload() -> dict:
    return {
        "schema_version": 1,
        "run_count": 1,
        "evaluated_signals": 2,
        "latest_run_date": "2026-05-07",
        "status": "ok",
        "summary": {
            "deep_selected_count": 1,
            "economy_only_count": 1,
            "portfolio_priority_count": 0,
            "deep_selected_avg_return_20d": 4.0,
            "economy_only_avg_return_20d": 2.0,
            "portfolio_priority_avg_return_20d": None,
            "deep_selected_hit_rate": 100.0,
            "economy_only_hit_rate": 0.0,
            "portfolio_priority_hit_rate": None,
            "avg_return_delta_20d": 2.0,
            "hit_rate_delta": 100.0,
        },
        "periods": [
            {
                "period": "2026-05",
                "deep_selected_count": 1,
                "economy_only_count": 1,
                "portfolio_priority_count": 0,
                "deep_selected_avg_return_20d": 4.0,
                "economy_only_avg_return_20d": 2.0,
                "portfolio_priority_avg_return_20d": None,
                "deep_selected_hit_rate": 100.0,
                "economy_only_hit_rate": 0.0,
                "portfolio_priority_hit_rate": None,
                "avg_return_delta_20d": 2.0,
                "hit_rate_delta": 100.0,
            }
        ],
        "latest_run": {
            "run_date": "2026-05-07",
            "trigger_range": [25, 75],
            "max_daily_ensemble": 3,
            "portfolio_priority": True,
            "deep_pass_count": 1,
            "selected_tickers": ["AAPL"],
            "skipped_due_to_priority": ["MSFT"],
            "router_budget_estimate": {
                "selected_count": 1,
                "estimated_incremental_cost_usd": 0.02,
                "estimated_monthly_cost_usd": 0.44,
            },
            "tickers": [
                {
                    "ticker": "AAPL",
                    "selected_for_deep": True,
                    "reason": "in_trigger_range",
                    "in_portfolio": False,
                    "conviction": 65,
                    "action": "buy",
                    "router_priority_score": 27.5,
                    "router_reason_codes": ["uncertainty_boundary"],
                    "skipped_due_to_priority": False,
                }
            ],
        },
    }


def _valid_analysis_performance_payload() -> dict:
    window_stats = {
        "sample_count": 12,
        "completed_count": 10,
        "avg_return": 2.5,
        "median_return": 1.2,
        "win_rate": 0.7,
        "loss_rate": 0.3,
        "directional_win_rate": 0.7,
        "missing_count": 2,
        "return_distribution": {"positive": 7, "negative": 3, "flat": 0},
        "triple_barrier_outcomes": {"hit": 6, "stop": 4},
    }
    ai_window_stats = {
        "sample_count": 8,
        "completed_count": 7,
        "missing_count": 1,
        "avg_return": 2.4,
        "median_return": 1.8,
        "best_return": 8.2,
        "worst_return": -3.1,
        "win_rate": 0.71,
        "loss_rate": 0.29,
    }
    ai_by_action = {
        action: {
            horizon: dict(ai_window_stats)
            for horizon in ("1d", "5d", "20d")
        }
        for action in ("buy", "watch", "avoid")
    }
    ai_bucket_by_action = {
        action: {
            horizon: dict(ai_window_stats)
            for horizon in ("5d", "20d")
        }
        for action in ("buy", "watch", "avoid")
    }
    return {
        "schema_version": 1,
        "as_of": "2026-05-07",
        "summary": {
            "sample_count": 12,
            "decision_count": 3,
            "completed_return_windows": ["1d", "5d"],
            "mode": "shadow_observational",
            "notes": ["Performance analytics are observational."],
        },
        "signal_performance": {
            "buy": {
                "5d": dict(window_stats),
            },
        },
        "conviction_calibration": {
            "status": "observational",
            "bucket_edges": ["65_80"],
            "buckets": {
                "65_80": {
                    "sample_count": 12,
                    "action_counts": {"buy": 12},
                    "avg_return_1d": 1.1,
                    "avg_return_5d": 2.5,
                    "avg_return_20d": None,
                    "buy_win_rate": 0.7,
                    "avoid_win_rate": None,
                },
            },
        },
        "regime_performance": {
            "bull": {
                "buy": {
                    "5d": dict(window_stats),
                },
            },
        },
        "factor_attribution": {
            "status": "observed_association",
            "missing_factor_sample_count": 0,
            "factors": {
                "momentum": {
                    "sample_count": 12,
                    "avg_score": 1.5,
                    "positive_score_count": 8,
                    "negative_score_count": 2,
                    "avg_forward_return_5d": 2.5,
                    "avg_forward_return_20d": None,
                    "best_action_context": {
                        "action": "buy",
                        "sample_count": 12,
                        "avg_return_5d": 2.5,
                    },
                    "worst_action_context": {
                        "action": "watch",
                        "sample_count": 0,
                        "avg_return_5d": None,
                    },
                },
            },
        },
        "action_change_reasons": [
            {
                "ticker": "AAPL",
                "previous_action": "watch",
                "current_action": "buy",
                "previous_conviction": 55,
                "current_conviction": 72,
                "previous_regime": "neutral",
                "current_regime": "bull",
                "reason_codes": ["conviction_up"],
                "summary": "Conviction improved.",
                "contributors": [
                    {
                        "factor": "momentum",
                        "previous": 1.0,
                        "current": 2.0,
                    }
                ],
            }
        ],
        "ai_recommendation_backtest": {
            "status": "ok",
            "basis": "final_action",
            "horizons": ["1d", "5d", "20d"],
            "summary": {
                "sample_count": 12,
                "completed_20d_count": 7,
                "best_action": "buy",
                "worst_action": "avoid",
                "notes": ["AI recommendation backtest is observational."],
            },
            "by_action": {
                action: {horizon: dict(stats) for horizon, stats in by_horizon.items()}
                for action, by_horizon in ai_by_action.items()
            },
            "conviction_buckets": {
                "65_80": {
                    "sample_count": 8,
                    "action_counts": {"buy": 6, "watch": 1, "avoid": 1},
                    "by_action": {
                        action: {horizon: dict(stats) for horizon, stats in by_horizon.items()}
                        for action, by_horizon in ai_bucket_by_action.items()
                    },
                },
                "80_100": {
                    "sample_count": 4,
                    "action_counts": {"buy": 2, "watch": 1, "avoid": 1},
                    "by_action": {
                        action: {horizon: dict(stats) for horizon, stats in by_horizon.items()}
                        for action, by_horizon in ai_bucket_by_action.items()
                    },
                },
            },
            "ticker_leaderboard": [
                {
                    "ticker": "AAPL",
                    "signals": 4,
                    "buy_signals": 4,
                    "watch_signals": 0,
                    "avoid_signals": 0,
                    "completed_5d_count": 4,
                    "completed_20d_count": 3,
                    "avg_return_5d": 1.6,
                    "avg_return_20d": 2.4,
                    "win_rate_5d": 0.75,
                    "win_rate_20d": 0.67,
                }
            ],
            "notable_examples": {
                "best": [
                    {
                        "signal_date": "2026-04-01",
                        "ticker": "AAPL",
                        "action": "buy",
                        "catalyst_tag": "earnings",
                        "regime": "bull",
                        "conviction": 72,
                        "return_5d": 1.6,
                        "return_20d": 8.2,
                    }
                ],
                "worst": [],
            },
        },
    }


def _valid_performance_trends_payload() -> dict:
    return {
        "schema_version": 1,
        "as_of": "2026-05-07",
        "monthly_budget_usd": 10.0,
        "runs": [
            {
                "run_date": "2026-05-07",
                "success": True,
                "total_cost_usd": 0.43,
                "llm_calls": 179,
                "hallucination_ratio": 0.1237,
                "validation_failure_count": 17,
                "deep_selected_count": 5,
                "budget_guard_would_block_count": 6,
            }
        ],
    }


def _valid_performance_baseline_payload() -> dict:
    return {
        "schema_version": 1,
        "as_of": "2026-05-07",
        "status": "ok",
        "latest_run_date": "2026-05-07",
        "monthly_budget_usd": 10.0,
        "json_health": {
            "status": "ok",
            "invalid_json_count": 0,
            "issues": [],
        },
        "cost": {
            "total_cost_usd": 0.43,
            "estimated_monthly_cost_usd": 9.5,
            "monthly_budget_usd": 10.0,
            "budget_usage_ratio": 0.95,
            "llm_calls": 179,
            "ticker_count_for_rate": 23,
            "llm_calls_per_ticker": 7.783,
            "deep_selected_count": 5,
            "routing_conflicted_count": 3,
            "budget_guard_would_block_count": 6,
            "budget_guard_blocked_count": 0,
        },
        "quality": {
            "validated_ticker_count": 283,
            "validation_failure_count": 17,
            "validation_failure_rate": 0.0601,
            "hallucination_warning_count": 35,
            "hallucination_ratio": 0.1237,
            "fact_warning_count": 8,
            "consistency_warning_count": 0,
        },
        "evidence": {
            "provider": "cache",
            "ticker_count": 23,
            "covered_ticker_count": 2,
            "coverage_ratio": 0.087,
            "average_coverage_score": 0.1,
            "average_freshness_score": 0.2,
            "candidate_ticker_count": 23,
            "searched_ticker_count": 0,
            "cache_ttl_hours": 24,
            "cache_hit_count": 2,
            "stale_cache_hit_count": 1,
            "cache_hit_ratio": 0.087,
            "stale_cache_hit_ratio": 0.5,
            "average_cache_age_hours": 12.0,
            "max_cache_age_hours": 24,
            "provider_candidate_count": 0,
            "status_counts": {"covered": 2},
            "priority_ticker_count": 2,
            "priority_covered_ticker_count": 1,
            "priority_coverage_ratio": 0.5,
            "priority_status_counts": {"covered": 1, "no_evidence": 1},
            "priority_refresh_reasons": {"router_selected": 2},
            "priority_refresh_candidate_count": 1,
            "priority_provider_error_count": 0,
            "priority_not_refreshed_count": 1,
            "priority_no_evidence_count": 1,
        },
        "signals": {
            "turnover_status": "ok",
            "avg_turnover": 0.047,
            "kelly_status": "ok",
        },
        "p1_readiness": {
            "status": "ready",
            "mode": "read_only_report",
            "tracks": {
                "search_evidence_provider": {
                    "status": "ready_for_limited_provider_validation",
                    "provider": "cache",
                    "candidate_ticker_count": 23,
                    "priority_ticker_count": 2,
                    "searched_ticker_count": 0,
                    "provider_candidate_count": 0,
                    "provider_call_count": 0,
                    "cache_hit_count": 2,
                    "stale_cache_hit_count": 1,
                    "provider_error_count": 0,
                    "provider_unavailable_count": 0,
                    "cache_error_count": 0,
                    "skipped_ticker_count": 21,
                    "cap_review_status": "cache_only_default",
                    "priority_refresh_candidate_ratio": 0.0,
                    "provider_issue_status": "clean",
                    "operational_issue_count": 0,
                    "stale_cache_reuse_status": "stale_cache_reused",
                    "status_counts": {"covered": 2},
                },
                "budget_guard": {
                    "status": "report_ready",
                    "mode": "shadow",
                    "enforce_review_status": "report_only_review_required",
                    "decision_counts": {"allow": 1, "would_block": 6},
                    "guarded_path_status_counts": {"allow": 1, "would_block": 2},
                    "would_block_count": 6,
                    "blocked_count": 0,
                    "guarded_path_count": 3,
                    "would_block_path_count": 2,
                    "blocked_path_count": 0,
                    "allow_path_count": 1,
                    "total_estimated_incremental_cost_usd": 0.12,
                },
                "analysis_performance": {
                    "status": "ready",
                    "mode": "shadow_observational",
                    "sample_count": 42,
                    "decision_count": 23,
                    "completed_return_windows": ["1d", "5d"],
                    "completed_return_window_count": 2,
                    "evaluated_signal_window_count": 4,
                    "conviction_bucket_count": 5,
                    "populated_conviction_bucket_count": 3,
                    "calibration_status": "observational",
                    "regime_count": 2,
                    "factor_count": 8,
                    "factor_attribution_status": "observed_association",
                    "missing_factor_sample_count": 5,
                    "action_change_reason_count": 2,
                    "action_change_coverage_ratio": 0.087,
                    "loop_readiness_status": "ready_for_quality_review",
                },
                "output_schema": {
                    "status": "ready",
                    "json_health_status": "ok",
                    "invalid_json_count": 0,
                    "issue_count": 0,
                },
            },
        },
    }


def _valid_quality_reliability_loop_payload() -> dict:
    return {
        "schema_version": 1,
        "as_of": "2026-05-21",
        "status": "partial",
        "summary": {
            "decision_quality_status": "ok",
            "artifact_reliability_status": "ok",
            "evidence_status": "partial",
            "cost_status": "reported",
        },
        "decision_quality": {
            "status": "ok",
            "loop_readiness_status": "ready_for_quality_review",
            "sample_count": 42,
            "completed_return_window_count": 2,
            "evaluated_signal_window_count": 4,
            "populated_conviction_bucket_count": 3,
            "factor_count": 8,
            "action_change_coverage_ratio": 0.5,
            "hallucination_ratio": 0.08,
            "validation_failure_rate": 0.02,
        },
        "artifact_reliability": {
            "status": "ok",
            "json_health_status": "ok",
            "invalid_json_count": 0,
            "issue_count": 0,
            "output_schema_status": "ready",
        },
        "evidence_quality": {
            "status": "partial",
            "ticker_count": 4,
            "covered_ticker_count": 2,
            "coverage_ratio": 0.5,
            "searched_ticker_count": 2,
            "priority_ticker_count": 2,
            "priority_covered_ticker_count": 1,
            "priority_coverage_ratio": 0.5,
            "status_counts": {"covered": 2, "provider_unavailable": 1},
            "priority_status_counts": {"covered": 1, "provider_unavailable": 1},
            "priority_refresh_reasons": {"router_selected": 2},
            "priority_refresh_candidate_count": 1,
            "priority_provider_error_count": 0,
            "priority_not_refreshed_count": 1,
            "priority_no_evidence_count": 1,
            "provider_issue_status": "provider_unavailable_seen",
            "operational_issue_count": 1,
        },
        "cost_and_runtime": {
            "status": "reported",
            "cost_policy": "report_only",
            "total_cost_usd": 1.25,
            "estimated_monthly_cost_usd": 27.5,
            "llm_calls": 220,
            "llm_calls_per_ticker": 9.565,
            "budget_guard_status": "report_ready",
            "budget_guard_mode": "shadow",
            "budget_guard_would_block_count": 4,
            "budget_guard_blocked_count": 0,
        },
        "trend_inputs": {
            "run_count": 2,
            "latest_run_date": "2026-05-21",
        },
        "warnings": ["provider_issue_seen"],
    }


def _valid_analysis_quality_payload() -> dict:
    run = {
        "run_date": "2026-05-07",
        "success": True,
        "daily_api_cost_usd": 0.42,
        "batch_count": 4,
        "validated_ticker_count": 10,
        "validation_failure_count": 2,
        "schema_violation_count": 1,
        "fact_warning_count": 1,
        "consistency_warning_count": 0,
        "hallucination_warning_count": 2,
        "hallucination_ratio": 0.2,
    }
    return {
        "schema_version": 1,
        "runs": [dict(run)],
        "latest": dict(run),
    }


def _valid_cost_log_payload() -> dict:
    run = {
        "run_date": "2026-05-07",
        "success": True,
        "total_cost_usd": 0.42,
        "profiles": {
            "economy": {
                "cost_usd": 0.12,
                "tokens": 1000,
                "input_tokens": 800,
                "cached_input_tokens": 600,
                "uncached_input_tokens": 200,
                "cache_hit_ratio": 0.75,
                "calls": 1,
                "models": {"gpt-5.4-mini": 1},
            },
            "deep": {
                "cost_usd": 0.30,
                "tokens": 2200,
                "input_tokens": 1000,
                "cached_input_tokens": 250,
                "uncached_input_tokens": 750,
                "cache_hit_ratio": 0.25,
                "calls": 1,
                "models": {"o3-mini": 1},
            },
        },
        "routing": {
            "ensemble_enabled": True,
            "eligible_count": 6,
            "selected_count": 3,
            "skipped_due_to_cap_count": 1,
            "conflicted_count": 2,
        },
        "budget_guard": {
            "mode": "shadow",
            "decision_counts": {"would_block": 1},
            "guarded_paths": {"ensemble_deep": "would_block"},
            "profile_counts": {"deep": 1},
            "would_block_count": 1,
            "blocked_count": 0,
            "total_estimated_incremental_cost_usd": 0.28,
        },
        "deep_pass_value": {
            "deep_cost_usd": 0.30,
            "selected_ticker_count": 3,
            "cost_per_selected_ticker_usd": 0.10,
            "share_of_total_cost": 0.7143,
            "worth_it_hint": "conflict_review_value",
        },
    }
    return {
        "schema_version": 1,
        "runs": [dict(run)],
        "latest": dict(run),
    }


def _valid_api_status_payload() -> dict:
    provider = {
        "overall_status": "active",
        "used_tickers": 1,
        "throttled_tickers": 0,
        "unavailable_tickers": 0,
        "failed_tickers": 0,
        "not_used_tickers": 0,
    }
    return {
        "schema_version": 1,
        "run_date": "2026-05-07",
        "log_path": "logs/pipeline/2026-05-07.jsonl",
        "pipeline_completed": True,
        "providers": {
            "yfinance": dict(provider),
            "alpha_vantage": dict(provider),
            "polygon": dict(provider),
            "fmp": dict(provider),
            "finnhub": dict(provider),
            "sec_edgar": dict(provider),
            "ir_rss": dict(provider),
        },
        "llm": {
            "used": True,
            "planned_batches": 1,
            "completed_batches": 1,
            "failed_batches": 0,
            "validation_failures": 0,
            "estimated_cost_usd": 0.0125,
            "latest_model": "gpt-5.4-mini",
            "models_used": {"gpt-5.4-mini": 1},
            "quality": {
                "run_date": "2026-05-07",
                "validated_ticker_count": 10,
                "validation_failure_count": 0,
                "schema_violation_count": 0,
                "fact_warning_count": 1,
                "consistency_warning_count": 0,
                "hallucination_warning_count": 1,
                "hallucination_ratio": 0.1,
            },
        },
    }


def _valid_api_ticker_matrix_payload() -> list[dict]:
    return [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "yfinance": "used",
            "alpha_vantage": "used",
            "polygon": "used",
            "fmp": "used",
            "finnhub": "used",
            "sec_edgar": "used",
            "ir_rss": "not_used",
        }
    ]


def _valid_validation_warnings_payload() -> dict:
    categories = [
        "schema_violation_count",
        "fact_warning_count",
        "consistency_warning_count",
        "hallucination_warning_count",
        "dropped_unsupported_count",
    ]
    row = {
        "date": "2026-05-07",
        "batch_count": 4,
        "validated_ticker_count": 10,
        "validation_failure_count": 2,
        "schema_violation_count": 0,
        "fact_warning_count": 1,
        "consistency_warning_count": 0,
        "hallucination_warning_count": 2,
        "dropped_unsupported_count": 0,
    }
    return {
        "schema_version": 1,
        "window_days": 14,
        "generated_at": "2026-05-07",
        "categories": list(categories),
        "totals": {
            "schema_violation_count": 0,
            "fact_warning_count": 1,
            "consistency_warning_count": 0,
            "hallucination_warning_count": 2,
            "dropped_unsupported_count": 0,
        },
        "series": [dict(row)],
    }


def _valid_signal_quality_payload() -> dict:
    return {
        "schema_version": 1,
        "ic_decay": {
            "status": "ok",
            "sample_sizes": {"1d": 30, "5d": 30, "20d": 25},
            "factors": [
                {
                    "factor": "momentum",
                    "ic": {"1d": 0.31, "5d": 0.22, "20d": None},
                    "n": {"1d": 30, "5d": 30, "20d": 25},
                    "monotonic_decay": True,
                }
            ],
        },
        "rolling_ic": {
            "status": "ok",
            "sample_size": 30,
            "horizon": 5,
            "window_days": 90,
            "step_days": 15,
            "factors": [
                {
                    "factor": "momentum",
                    "series": [
                        {
                            "window_end": "2026-05-07",
                            "ic": 0.22,
                            "n": 30,
                        }
                    ],
                    "latest_ic": 0.22,
                    "lifetime_avg_ic": 0.18,
                    "fatigue": False,
                }
            ],
        },
        "kelly": {
            "status": "ok",
            "horizon": 5,
            "haircut": 0.5,
            "by_direction": {
                "bull": {
                    "status": "ok",
                    "n": 30,
                    "hit_rate": 0.7,
                    "avg_win": 2.0,
                    "avg_loss": 1.0,
                    "payoff_ratio": 2.0,
                    "kelly_full": 0.55,
                    "kelly_half": 0.275,
                },
                "bear": {
                    "status": "insufficient_data",
                    "n": 3,
                },
            },
        },
        "turnover": {
            "status": "ok",
            "sample_size": 2,
            "avg_turnover": 0.25,
            "points": [
                {
                    "date": "2026-05-07",
                    "tickers": 10,
                    "turnover": 0.25,
                }
            ],
        },
    }


class OutputHealthCheckTests(unittest.TestCase):
    def test_output_health_result_warnings_do_not_fail_check(self) -> None:
        from src.output.health_common import OutputHealthIssue
        from src.output.health_check import OutputHealthResult

        result = OutputHealthResult(
            issues=(),
            warnings=(
                OutputHealthIssue(
                    "cost_budget_over_target",
                    "output/data/performance_baseline.json",
                    "budget_usage_ratio=1.853",
                ),
            ),
        )

        self.assertTrue(result.ok)
        summary = result.format_summary()
        self.assertIn("output health check passed", summary)
        self.assertIn("output health check warning(s): 1", summary)
        self.assertIn("cost_budget_over_target", summary)

    def test_detects_invalid_source_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            source.mkdir(parents=True)
            mirror.mkdir(parents=True)
            (source / "index.json").write_text('{"schema_version": ', encoding="utf-8")

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("invalid_json", {issue.code for issue in result.issues})

    def test_detects_web_public_mirror_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "index.json", {"schema_version": 1, "tickers": []})
            _write_json(root / "web" / "public" / "output" / "data" / "index.json", {"schema_version": 1, "tickers": ["AAPL"]})

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_mismatch", {issue.code for issue in result.issues})

    def test_warns_on_web_only_stale_legacy_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(
                source / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(
                source / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )
            _write_json(
                mirror / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(
                mirror / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )
            _write_json(
                mirror / "dashboard.json",
                {"schema_version": 1, "days": [{"date": "2026-04-15"}]},
            )

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())
        self.assertIn("web_only_stale_candidate", {warning.code for warning in result.warnings})

    def test_detects_source_current_artifact_date_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(
                source / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(
                source / "dashboard.json",
                {"schema_version": 1, "days": [{"date": "2026-04-15"}]},
            )
            _write_json(
                source / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )
            _write_json(
                mirror / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(
                mirror / "dashboard.json",
                {"schema_version": 1, "days": [{"date": "2026-04-15"}]},
            )
            _write_json(
                mirror / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("source_date_mismatch", {issue.code for issue in result.issues})

    def test_detects_source_current_artifact_missing_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(
                source / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(source / "dashboard.json", {"schema_version": 1, "days": [{}]})
            _write_json(
                source / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )
            _write_json(
                mirror / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(mirror / "dashboard.json", {"schema_version": 1, "days": [{}]})
            _write_json(
                mirror / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("source_date_missing", {issue.code for issue in result.issues})

    def test_warns_on_web_only_optional_legacy_dashboard_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(
                source / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(
                source / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )
            _write_json(
                mirror / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": []},
            )
            _write_json(
                mirror / "dashboard_history.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )
            _write_json(
                mirror / "dashboard.json",
                {"schema_version": 1, "days": [{"date": "2026-05-26"}]},
            )

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())
        self.assertIn("optional_legacy_artifact_present", {warning.code for warning in result.warnings})

    def test_passes_when_index_ticker_artifacts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(
                source / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": [{"ticker": "XYL"}]},
            )
            _write_json(
                mirror / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": [{"ticker": "XYL"}]},
            )
            _write_json(
                source / "tickers" / "XYL" / "latest.json",
                {"schema_version": 1, "ticker": "XYL"},
            )
            _write_json(
                source / "tickers" / "XYL" / "history.json",
                {"schema_version": 1, "ticker": "XYL", "days": []},
            )
            _write_json(
                mirror / "tickers" / "XYL" / "latest.json",
                {"schema_version": 1, "ticker": "XYL"},
            )
            _write_json(
                mirror / "tickers" / "XYL" / "history.json",
                {"schema_version": 1, "ticker": "XYL", "days": []},
            )
            note = root / "output" / "tickers" / "XYL" / "2026-05-26.md"
            note.parent.mkdir(parents=True)
            note.write_text("# XYL 2026-05-26\n", encoding="utf-8")

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_detects_missing_index_ticker_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(
                source / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": [{"ticker": "XYL"}]},
            )
            _write_json(
                mirror / "index.json",
                {"schema_version": 1, "date": "2026-05-26", "tickers": [{"ticker": "XYL"}]},
            )

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("ticker_artifact_missing", {issue.code for issue in result.issues})

    def test_warns_on_cost_increase_and_budget_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(source / "index.json", {"schema_version": 1, "date": "2026-05-26", "tickers": []})
            _write_json(mirror / "index.json", {"schema_version": 1, "date": "2026-05-26", "tickers": []})

            latest = json.loads(json.dumps(_valid_cost_log_payload()["latest"]))
            latest["run_date"] = "2026-05-27"
            latest["total_cost_usd"] = 0.42
            latest["routing"]["eligible_count"] = 25
            latest["budget_guard"]["would_block_count"] = 2
            previous = json.loads(json.dumps(_valid_cost_log_payload()["latest"]))
            previous["run_date"] = "2026-05-22"
            previous["total_cost_usd"] = 0.30
            previous["routing"]["eligible_count"] = 25
            previous["budget_guard"]["would_block_count"] = 0
            cost_log = {
                "schema_version": 1,
                "latest": latest,
                "runs": [latest, previous],
            }
            _write_json(source / "cost_log.json", cost_log)
            _write_json(mirror / "cost_log.json", cost_log)

            baseline = _valid_performance_baseline_payload()
            baseline["as_of"] = "2026-05-27"
            baseline["latest_run_date"] = "2026-05-27"
            baseline["cost"]["budget_usage_ratio"] = 1.2
            _write_json(source / "performance_baseline.json", baseline)
            _write_json(mirror / "performance_baseline.json", baseline)

            result = check_output_health(root)

        warning_codes = {warning.code for warning in result.warnings}
        self.assertTrue(result.ok, result.format_summary())
        self.assertIn("cost_increased_vs_comparable_run", warning_codes)
        self.assertIn("cost_budget_over_target", warning_codes)
        self.assertIn("budget_guard_would_block", warning_codes)
        cost_warning = next(
            warning for warning in result.warnings if warning.code == "cost_increased_vs_comparable_run"
        )
        self.assertIn("profiles=", cost_warning.detail)
        self.assertIn("economy", cost_warning.detail)
        self.assertIn("standard", cost_warning.detail)
        self.assertIn("deep", cost_warning.detail)
        self.assertIn("routing=", cost_warning.detail)
        self.assertIn("selected_count", cost_warning.detail)
        self.assertIn("llm_calls_per_ticker", cost_warning.detail)
        self.assertIn("output_tokens_delta", cost_warning.detail)

    def test_warns_on_evidence_provider_error_and_zero_priority_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(source / "index.json", {"schema_version": 1, "date": "2026-05-26", "tickers": []})
            _write_json(mirror / "index.json", {"schema_version": 1, "date": "2026-05-26", "tickers": []})
            payload = {
                "schema_version": 1,
                "date": "2026-05-26",
                "provider": "cache",
                "items": [],
                "by_ticker": {
                    "AAPL": {
                        "evidence_count": 0,
                        "evidence_status": "provider_error",
                        "provider_status": "provider_error",
                        "priority_for_refresh": True,
                        "priority_refresh_reasons": ["router_selected"],
                        "cache_source_date": "",
                        "cache_age_hours": 0,
                        "coverage_score": 0.0,
                        "freshness_score": 0.0,
                    }
                },
                "run_summary": {
                    "candidate_ticker_count": 1,
                    "searched_ticker_count": 0,
                    "cache_hit_count": 0,
                    "cache_error_count": 0,
                    "cache_ttl_hours": 24,
                    "stale_cache_hit_count": 0,
                    "status_counts": {"provider_error": 1},
                    "priority_tickers": ["AAPL"],
                    "priority_ticker_count": 1,
                    "priority_refresh_reasons": {"router_selected": 1},
                    "priority_status_counts": {"provider_error": 1},
                    "priority_refresh_candidate_count": 1,
                    "provider_candidate_count": 1,
                    "provider_call_count": 0,
                    "provider_error_count": 1,
                    "skipped_ticker_count": 0,
                },
            }
            _write_json(source / "search_evidence.json", payload)
            _write_json(mirror / "search_evidence.json", payload)

            result = check_output_health(root)

        warning_codes = {warning.code for warning in result.warnings}
        self.assertTrue(result.ok, result.format_summary())
        self.assertIn("evidence_provider_error", warning_codes)
        self.assertIn("priority_evidence_zero_coverage", warning_codes)

    def test_warns_on_evidence_provider_error_from_status_maps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            _write_json(source / "index.json", {"schema_version": 1, "date": "2026-05-26", "tickers": []})
            _write_json(mirror / "index.json", {"schema_version": 1, "date": "2026-05-26", "tickers": []})
            payload = _valid_search_evidence_payload()
            payload["date"] = "2026-05-26"
            payload["by_ticker"]["AAPL"].update(
                {
                    "evidence_count": 0,
                    "evidence_status": "provider_error",
                    "provider_status": "provider_error",
                    "priority_for_refresh": True,
                    "priority_refresh_reasons": ["router_selected"],
                    "cache_source_date": "",
                    "cache_age_hours": 0,
                }
            )
            payload["run_summary"].update(
                {
                    "candidate_ticker_count": 1,
                    "status_counts": {"provider_error": 1},
                    "priority_tickers": ["AAPL"],
                    "priority_ticker_count": 1,
                    "priority_refresh_reasons": {"router_selected": 1},
                    "priority_status_counts": {"provider_error": 1},
                    "priority_refresh_candidate_count": 1,
                    "provider_candidate_count": 1,
                    "provider_call_count": 0,
                }
            )
            payload["run_summary"].pop("provider_error_count", None)
            _write_json(source / "search_evidence.json", payload)
            _write_json(mirror / "search_evidence.json", payload)

            result = check_output_health(root)

        warning_codes = {warning.code for warning in result.warnings}
        self.assertTrue(result.ok, result.format_summary())
        self.assertIn("evidence_provider_error", warning_codes)
        self.assertIn("priority_evidence_zero_coverage", warning_codes)

    def test_detects_missing_ticker_mirror_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "tickers" / "AAPL" / "latest.json", {"ticker": "AAPL"})
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})

    def test_detects_merge_conflict_marker_in_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            source.mkdir(parents=True)
            mirror.mkdir(parents=True)
            (source / "price_history.csv").write_text("date,ticker\n<<<<<<< HEAD\n", encoding="utf-8")

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("merge_conflict_marker", {issue.code for issue in result.issues})

    def test_passes_when_source_and_web_public_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "index.json", {"schema_version": 1, "tickers": []})
            _write_json(root / "web" / "public" / "output" / "data" / "index.json", {"schema_version": 1, "tickers": []})
            _write_json(root / "output" / "data" / "tickers" / "AAPL" / "latest.json", {"ticker": "AAPL"})
            _write_json(root / "web" / "public" / "output" / "data" / "tickers" / "AAPL" / "latest.json", {"ticker": "AAPL"})

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_search_evidence_is_part_of_default_web_mirror_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "output" / "data" / "search_evidence.json",
                {"schema_version": 1, "date": "2026-05-07", "items": [], "by_ticker": {}, "run_summary": {}},
            )
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})

    def test_detects_search_evidence_missing_cache_summary_fields(self) -> None:
        payload = {
            "schema_version": 1,
            "date": "2026-05-07",
            "provider": "cache",
            "items": [],
            "by_ticker": {},
            "run_summary": {
                "candidate_ticker_count": 0,
                "searched_ticker_count": 0,
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "search_evidence.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "search_evidence.json", payload)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                issue.code == "invalid_search_evidence" and "cache summary" in issue.detail
                for issue in result.issues
            )
        )

    def test_output_health_check_rejects_malformed_search_evidence_priority_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = _valid_search_evidence_payload()
            payload["by_ticker"]["AAPL"]["priority_refresh_reasons"] = ["router_selected", 123]
            _write_json(root / "output" / "data" / "search_evidence.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "search_evidence.json", payload)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                issue.code == "invalid_search_evidence"
                and "priority_refresh_reasons must be a list of strings" in issue.detail
                for issue in result.issues
            )
        )

    def test_detects_search_evidence_invalid_cache_summary_values(self) -> None:
        cases = (
            ("cache_hit_count", -1),
            ("cache_hit_count", "0"),
            ("cache_error_count", -1),
            ("cache_ttl_hours", -1),
            ("cache_ttl_hours", "24"),
            ("stale_cache_hit_count", -1),
            ("status_counts", []),
            ("status_counts", {"no_evidence": -1}),
            ("status_counts", {"no_evidence": "1"}),
            ("priority_refresh_reasons", []),
            ("priority_refresh_reasons", {"router_selected": -1}),
            ("priority_refresh_reasons", {"router_selected": "1"}),
            ("priority_status_counts", []),
            ("priority_status_counts", {"covered": -1}),
            ("priority_status_counts", {"covered": "1"}),
            ("priority_refresh_candidate_count", -1),
            ("priority_refresh_candidate_count", "0"),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                run_summary = {
                    "candidate_ticker_count": 1,
                    "searched_ticker_count": 0,
                    "cache_hit_count": 0,
                    "cache_error_count": 0,
                    "cache_ttl_hours": 24,
                    "stale_cache_hit_count": 0,
                    "status_counts": {"no_evidence": 1},
                    "priority_refresh_reasons": {"router_selected": 1},
                    "priority_status_counts": {"no_evidence": 1},
                    "priority_refresh_candidate_count": 0,
                }
                run_summary[field] = bad_value
                payload = {
                    "schema_version": 1,
                    "date": "2026-05-07",
                    "provider": "cache",
                    "items": [],
                    "by_ticker": {},
                    "run_summary": run_summary,
                }
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "search_evidence.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "search_evidence.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_search_evidence" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_search_evidence_missing_ticker_cache_metadata(self) -> None:
        payload = {
            "schema_version": 1,
            "date": "2026-05-07",
            "provider": "cache",
            "items": [],
            "by_ticker": {
                "AAPL": {
                    "evidence_count": 0,
                    "evidence_status": "no_evidence",
                },
            },
            "run_summary": {
                "candidate_ticker_count": 1,
                "searched_ticker_count": 0,
                "cache_hit_count": 0,
                "cache_error_count": 0,
                "cache_ttl_hours": 24,
                "stale_cache_hit_count": 0,
                "status_counts": {"no_evidence": 1},
                "priority_refresh_reasons": {"router_selected": 1},
                "priority_status_counts": {"no_evidence": 1},
                "priority_refresh_candidate_count": 0,
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "search_evidence.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "search_evidence.json", payload)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                issue.code == "invalid_search_evidence" and "ticker summary" in issue.detail
                for issue in result.issues
            )
        )

    def test_detects_search_evidence_invalid_ticker_cache_age(self) -> None:
        for bad_age in (-1, "24"):
            with self.subTest(bad_age=bad_age):
                payload = {
                    "schema_version": 1,
                    "date": "2026-05-07",
                    "provider": "cache",
                    "items": [],
                    "by_ticker": {
                        "AAPL": {
                            "evidence_count": 0,
                            "evidence_status": "no_evidence",
                            "provider_status": "not_requested",
                            "priority_for_refresh": False,
                            "priority_refresh_reasons": [],
                            "cache_source_date": "",
                            "cache_age_hours": bad_age,
                        },
                    },
                    "run_summary": {
                        "candidate_ticker_count": 1,
                        "searched_ticker_count": 0,
                        "cache_hit_count": 0,
                        "cache_error_count": 0,
                        "cache_ttl_hours": 24,
                        "stale_cache_hit_count": 0,
                        "status_counts": {"no_evidence": 1},
                        "priority_refresh_reasons": {"router_selected": 1},
                        "priority_status_counts": {"no_evidence": 1},
                        "priority_refresh_candidate_count": 0,
                    },
                }
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "search_evidence.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "search_evidence.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_search_evidence" and "cache_age_hours" in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_search_evidence_invalid_ticker_metadata_types(self) -> None:
        cases = (
            ("evidence_status", None),
            ("provider_status", None),
            ("priority_for_refresh", "false"),
            ("cache_source_date", None),
        )
        for field, bad_value in cases:
            with self.subTest(field=field):
                summary = {
                    "evidence_count": 0,
                    "evidence_status": "no_evidence",
                    "provider_status": "not_requested",
                    "priority_for_refresh": False,
                    "priority_refresh_reasons": [],
                    "cache_source_date": "",
                    "cache_age_hours": 0,
                }
                summary[field] = bad_value
                payload = {
                    "schema_version": 1,
                    "date": "2026-05-07",
                    "provider": "cache",
                    "items": [],
                    "by_ticker": {"AAPL": summary},
                    "run_summary": {
                        "candidate_ticker_count": 1,
                        "searched_ticker_count": 0,
                        "cache_hit_count": 0,
                        "cache_error_count": 0,
                        "cache_ttl_hours": 24,
                        "stale_cache_hit_count": 0,
                        "status_counts": {"no_evidence": 1},
                        "priority_refresh_reasons": {"router_selected": 1},
                        "priority_status_counts": {"no_evidence": 1},
                        "priority_refresh_candidate_count": 0,
                    },
                }
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "search_evidence.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "search_evidence.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_search_evidence" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_search_audit_is_part_of_default_web_mirror_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "output" / "data" / "search_audit.json",
                {"schema_version": 1, "date": "2026-05-07", "tickers": [], "run_summary": {}},
            )
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})
        self.assertTrue(any("search_audit.json" in issue.path for issue in result.issues))

    def test_detects_invalid_search_audit_root_shape(self) -> None:
        cases = (
            ("run_summary", None),
            ("tickers", {}),
        )
        for field, replacement in cases:
            with self.subTest(field=field):
                payload = _valid_search_audit_payload()
                if replacement is None:
                    payload.pop(field)
                else:
                    payload[field] = replacement
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "search_audit.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "search_audit.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_search_audit" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_search_audit_summary_ticker_and_issue_values(self) -> None:
        cases = (
            ("run_summary.checked_claims", lambda payload: payload["run_summary"].update({"checked_claims": -1})),
            ("run_summary.issue_count", lambda payload: payload["run_summary"].update({"issue_count": "1"})),
            ("ticker.verdict", lambda payload: payload["tickers"][0].update({"verdict": "fail"})),
            ("ticker.checked_claims", lambda payload: payload["tickers"][0].update({"checked_claims": -1})),
            ("issue.status", lambda payload: payload["tickers"][0]["issues"][0].update({"status": "unknown"})),
            ("issue.claim", lambda payload: payload["tickers"][0]["issues"][0].update({"claim": None})),
            ("issue.match_score", lambda payload: payload["tickers"][0]["issues"][0].update({"match_score": 1.2})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_search_audit_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "search_audit.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "search_audit.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_search_audit" and field.split(".")[-1] in issue.detail
                        for issue in result.issues
                    )
                )

    def test_performance_artifacts_are_part_of_default_web_mirror_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "output" / "data" / "performance_baseline.json",
                {
                    "schema_version": 1,
                    "status": "ok",
                    "json_health": {"invalid_json_count": 0},
                },
            )
            _write_json(
                root / "output" / "data" / "performance_trends.json",
                {"schema_version": 1, "runs": []},
            )
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})
        self.assertTrue(any("performance_baseline.json" in issue.path for issue in result.issues))
        self.assertTrue(any("performance_trends.json" in issue.path for issue in result.issues))

    def test_quality_reliability_loop_is_part_of_default_web_mirror_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "output" / "data" / "quality_reliability_loop.json",
                _valid_quality_reliability_loop_payload(),
            )
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})
        self.assertTrue(any("quality_reliability_loop.json" in issue.path for issue in result.issues))

    def test_accepts_quality_reliability_loop_failed_json_health_status(self) -> None:
        payload = _valid_quality_reliability_loop_payload()
        payload["status"] = "failed"
        payload["summary"]["artifact_reliability_status"] = "failed"
        payload["artifact_reliability"].update(
            {
                "status": "failed",
                "json_health_status": "invalid_json",
                "invalid_json_count": 1,
                "issue_count": 1,
                "output_schema_status": "needs_attention",
            }
        )
        payload["warnings"] = ["invalid_json_detected"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "quality_reliability_loop.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "quality_reliability_loop.json", payload)

            result = check_output_health(root)

        self.assertTrue(
            all(issue.code != "invalid_quality_reliability_loop" for issue in result.issues),
            result.format_summary(),
        )

    def test_writer_quality_reliability_loop_payload_passes_health_shape(self) -> None:
        from src.output.performance import write_performance_outputs

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)
            _write_json(root / "output" / "data" / "cost_log.json", _valid_cost_log_payload())
            _write_json(root / "output" / "data" / "analysis_quality.json", _valid_analysis_quality_payload())
            _write_json(root / "output" / "data" / "analysis_performance.json", _valid_analysis_performance_payload())
            _write_json(root / "output" / "data" / "search_evidence.json", _valid_search_evidence_payload())
            _write_json(root / "output" / "data" / "signal_quality.json", _valid_signal_quality_payload())

            write_performance_outputs(
                output_root=root / "output",
                project_root=root,
                run_date=date(2026, 5, 21),
            )
            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_writer_empty_input_performance_payloads_pass_health_shape(self) -> None:
        from src.output.performance import write_performance_outputs

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            write_performance_outputs(
                output_root=root / "output",
                project_root=root,
                run_date=date(2026, 5, 21),
            )
            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_detects_invalid_quality_reliability_loop_shape_when_present(self) -> None:
        cases = (
            ("schema_version", 0),
            ("as_of", ""),
            ("status", "broken"),
            ("summary", []),
            ("decision_quality", []),
            ("artifact_reliability", []),
            ("evidence_quality", []),
            ("cost_and_runtime", []),
            ("trend_inputs", []),
            ("warnings", {}),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_quality_reliability_loop_payload()
                payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "quality_reliability_loop.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "quality_reliability_loop.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_quality_reliability_loop" and field in issue.detail
                        for issue in result.issues
                    ),
                    result.format_summary(),
                )

    def test_detects_invalid_quality_reliability_loop_nested_values(self) -> None:
        cases = (
            (
                "decision_quality_status",
                lambda payload: payload["summary"].update({"decision_quality_status": "ready"}),
            ),
            ("notes", lambda payload: payload["summary"].update({"notes": [None]})),
            ("decision_quality.status", lambda payload: payload["decision_quality"].update({"status": "ready"})),
            ("sample_count", lambda payload: payload["decision_quality"].update({"sample_count": -1})),
            (
                "action_change_coverage_ratio",
                lambda payload: payload["decision_quality"].update({"action_change_coverage_ratio": 1.2}),
            ),
            (
                "invalid_json_count",
                lambda payload: payload["artifact_reliability"].update({"invalid_json_count": -1}),
            ),
            (
                "issue_count",
                lambda payload: payload["artifact_reliability"].update({"issue_count": -1}),
            ),
            ("issues", lambda payload: payload["artifact_reliability"].update({"issues": {}})),
            ("coverage_ratio", lambda payload: payload["evidence_quality"].update({"coverage_ratio": 1.2})),
            (
                "status_counts",
                lambda payload: payload["evidence_quality"].update({"status_counts": {"covered": "2"}}),
            ),
            (
                "priority_refresh_reasons",
                lambda payload: payload["evidence_quality"].update(
                    {"priority_refresh_reasons": {"router_selected": "2"}}
                ),
            ),
            (
                "priority_refresh_candidate_count",
                lambda payload: payload["evidence_quality"].update({"priority_refresh_candidate_count": -1}),
            ),
            (
                "priority_provider_error_count",
                lambda payload: payload["evidence_quality"].update({"priority_provider_error_count": "0"}),
            ),
            (
                "priority_not_refreshed_count",
                lambda payload: payload["evidence_quality"].update({"priority_not_refreshed_count": -1}),
            ),
            (
                "priority_no_evidence_count",
                lambda payload: payload["evidence_quality"].update({"priority_no_evidence_count": -1}),
            ),
            ("cost_policy", lambda payload: payload["cost_and_runtime"].update({"cost_policy": "enforce"})),
            ("total_cost_usd", lambda payload: payload["cost_and_runtime"].update({"total_cost_usd": -0.01})),
            ("llm_calls", lambda payload: payload["cost_and_runtime"].update({"llm_calls": "220"})),
            ("run_count", lambda payload: payload["trend_inputs"].update({"run_count": -1})),
            ("warnings", lambda payload: payload.update({"warnings": [None]})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_quality_reliability_loop_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "quality_reliability_loop.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "quality_reliability_loop.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                expected_detail = field.split(".")[-1]
                self.assertTrue(
                    any(
                        issue.code == "invalid_quality_reliability_loop" and expected_detail in issue.detail
                        for issue in result.issues
                    ),
                    result.format_summary(),
                )

    def test_analysis_performance_is_part_of_default_web_mirror_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "output" / "data" / "analysis_performance.json",
                {
                    "schema_version": 1,
                    "as_of": "2026-05-04",
                    "summary": {},
                    "signal_performance": {},
                    "conviction_calibration": {},
                    "regime_performance": {},
                    "factor_attribution": {},
                    "action_change_reasons": [],
                },
            )
            (root / "web" / "public" / "output" / "data").mkdir(parents=True)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("mirror_missing", {issue.code for issue in result.issues})
        self.assertTrue(any("analysis_performance.json" in issue.path for issue in result.issues))

    def test_detects_invalid_analysis_performance_root_shape(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("as_of", None),
            ("summary", []),
            ("signal_performance", []),
            ("conviction_calibration", []),
            ("regime_performance", []),
            ("factor_attribution", []),
            ("action_change_reasons", {}),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_analysis_performance_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "analysis_performance.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_analysis_performance" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_analysis_performance_nested_values(self) -> None:
        cases = (
            ("sample_count", lambda payload: payload["summary"].update({"sample_count": "12"})),
            ("completed_return_windows", lambda payload: payload["summary"].update({"completed_return_windows": [None]})),
            ("win_rate", lambda payload: payload["signal_performance"]["buy"]["5d"].update({"win_rate": 1.2})),
            ("return_distribution", lambda payload: payload["signal_performance"]["buy"]["5d"].update({"return_distribution": {"positive": 7, "negative": -1, "flat": 0}})),
            ("triple_barrier_outcomes", lambda payload: payload["signal_performance"]["buy"]["5d"].update({"triple_barrier_outcomes": {"hit": "6"}})),
            ("action_counts", lambda payload: payload["conviction_calibration"]["buckets"]["65_80"].update({"action_counts": {"buy": "12"}})),
            ("buy_win_rate", lambda payload: payload["conviction_calibration"]["buckets"]["65_80"].update({"buy_win_rate": 1.2})),
            ("completed_count", lambda payload: payload["regime_performance"]["bull"]["buy"]["5d"].update({"completed_count": -1})),
            ("missing_factor_sample_count", lambda payload: payload["factor_attribution"].update({"missing_factor_sample_count": -1})),
            ("avg_score", lambda payload: payload["factor_attribution"]["factors"]["momentum"].update({"avg_score": "1.5"})),
            ("best_action_context", lambda payload: payload["factor_attribution"]["factors"]["momentum"].update({"best_action_context": []})),
            ("reason_codes", lambda payload: payload["action_change_reasons"][0].update({"reason_codes": ["conviction_up", None]})),
            ("current_conviction", lambda payload: payload["action_change_reasons"][0].update({"current_conviction": "72"})),
            ("contributors", lambda payload: payload["action_change_reasons"][0]["contributors"].append([])),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_analysis_performance_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "analysis_performance.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_analysis_performance" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_ai_recommendation_backtest_shape(self) -> None:
        cases = (
            (
                "basis",
                lambda payload: payload["ai_recommendation_backtest"].update({"basis": "llm_direction"}),
            ),
            (
                "horizons",
                lambda payload: payload["ai_recommendation_backtest"].update({"horizons": "1d,5d,20d"}),
            ),
            (
                "horizons",
                lambda payload: payload["ai_recommendation_backtest"].update({"horizons": ["bogus"]}),
            ),
            (
                "horizons",
                lambda payload: payload["ai_recommendation_backtest"].update(
                    {"horizons": ["1d", "5d", "20d", "20d"]}
                ),
            ),
            (
                "status",
                lambda payload: payload["ai_recommendation_backtest"].update(
                    {"status": "partial", "horizons": ["bogus"], "by_action": {"buy": {}}}
                ),
            ),
            (
                "by_action",
                lambda payload: payload["ai_recommendation_backtest"].update({"by_action": {"buy": {}}}),
            ),
            (
                "completed_20d_count",
                lambda payload: payload["ai_recommendation_backtest"]["summary"].update(
                    {"completed_20d_count": -1}
                ),
            ),
            (
                "win_rate",
                lambda payload: payload["ai_recommendation_backtest"]["by_action"]["buy"]["20d"].update(
                    {"win_rate": 1.2}
                ),
            ),
            (
                "ticker_leaderboard",
                lambda payload: payload["ai_recommendation_backtest"].update({"ticker_leaderboard": {}}),
            ),
            (
                "notable_examples",
                lambda payload: payload["ai_recommendation_backtest"].update({"notable_examples": []}),
            ),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = json.loads(json.dumps(_valid_analysis_performance_payload()))
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "analysis_performance.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_analysis_performance" and field in issue.detail
                        for issue in result.issues
                    ),
                    result.format_summary(),
                )

    def test_allows_missing_ai_recommendation_backtest_for_backward_compatibility(self) -> None:
        payload = _valid_analysis_performance_payload()
        payload.pop("ai_recommendation_backtest")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "analysis_performance.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

            result = check_output_health(root)

        self.assertTrue(
            all(
                issue.code != "invalid_analysis_performance"
                or "ai_recommendation_backtest" not in issue.detail
                for issue in result.issues
            ),
            result.format_summary(),
        )

    def test_generated_ai_recommendation_backtest_allows_blank_optional_example_metadata(self) -> None:
        from src.output.analysis_performance import build_analysis_performance_payload
        from src.types import MarketRegime

        signal_rows = [
            {
                "signal_date": "2026-04-02",
                "ticker": "AAPL",
                "action": "buy",
                "conviction": "72",
                "catalyst_tag": "",
                "regime": "",
                "return_1d": "+1.00%",
                "return_5d": "+3.00%",
                "return_20d": "+8.00%",
                "evaluated_1d": "True",
                "evaluated_5d": "True",
                "evaluated_20d": "True",
                "barrier_label": "hit",
                "factors_json": '{"momentum": 1.5}',
            }
        ]
        payload = build_analysis_performance_payload(
            signal_rows,
            run_date=date(2026, 5, 1),
            decisions=[],
            market_regime=MarketRegime(regime="neutral"),
        )
        self.assertEqual(payload["ai_recommendation_backtest"]["notable_examples"]["best"][0]["catalyst_tag"], "")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "analysis_performance.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_generated_sparse_ai_recommendation_backtest_insufficient_data_passes_health_check(self) -> None:
        from src.output.analysis_performance import build_analysis_performance_payload
        from src.types import MarketRegime

        payload = build_analysis_performance_payload(
            [],
            run_date=date(2026, 5, 1),
            decisions=[],
            market_regime=MarketRegime(regime="neutral"),
        )
        self.assertEqual(payload["ai_recommendation_backtest"]["status"], "insufficient_data")
        self.assertEqual(payload["ai_recommendation_backtest"]["by_action"], {})
        self.assertEqual(payload["ai_recommendation_backtest"]["conviction_buckets"], {})

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "analysis_performance.json", payload)
            _write_json(root / "web" / "public" / "output" / "data" / "analysis_performance.json", payload)

            result = check_output_health(root)

        self.assertTrue(result.ok, result.format_summary())

    def test_detects_invalid_api_status_root_shape(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("run_date", None),
            ("pipeline_completed", "true"),
            ("providers", []),
            ("llm", []),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_api_status_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "api_status.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "api_status.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_api_status" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_api_status_nested_values(self) -> None:
        cases = (
            ("overall_status", lambda payload: payload["providers"]["yfinance"].update({"overall_status": "broken"})),
            ("used_tickers", lambda payload: payload["providers"]["yfinance"].update({"used_tickers": -1})),
            ("planned_batches", lambda payload: payload["llm"].update({"planned_batches": "1"})),
            ("estimated_cost_usd", lambda payload: payload["llm"].update({"estimated_cost_usd": -0.01})),
            ("models_used", lambda payload: payload["llm"].update({"models_used": {"gpt-5.4-mini": "1"}})),
            ("validation_failure_count", lambda payload: payload["llm"]["quality"].update({"validation_failure_count": -1})),
            ("hallucination_ratio", lambda payload: payload["llm"]["quality"].update({"hallucination_ratio": 1.2})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_api_status_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "api_status.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "api_status.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_api_status" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_api_ticker_matrix_shape(self) -> None:
        cases = (
            ("api_ticker_matrix", {}),
            ("ticker", [{"ticker": "", "name": "Apple Inc.", "sector": "Technology"}]),
            ("yfinance", [{**_valid_api_ticker_matrix_payload()[0], "yfinance": "broken"}]),
            ("name", [{**_valid_api_ticker_matrix_payload()[0], "name": None}]),
        )
        for field, payload in cases:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "api_ticker_matrix.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "api_ticker_matrix.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_api_ticker_matrix" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_validation_warnings_root_shape(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("window_days", "14"),
            ("generated_at", None),
            ("categories", {}),
            ("totals", []),
            ("series", {}),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_validation_warnings_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "validation_warnings.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "validation_warnings.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_validation_warnings" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_validation_warnings_values(self) -> None:
        cases = (
            ("categories", lambda payload: payload.update({"categories": ["fact_warning_count", None]})),
            ("totals", lambda payload: payload["totals"].update({"fact_warning_count": "1"})),
            ("series", lambda payload: payload["series"].append([])),
            ("date", lambda payload: payload["series"][0].update({"date": ""})),
            ("validated_ticker_count", lambda payload: payload["series"][0].update({"validated_ticker_count": -1})),
            ("fact_warning_count", lambda payload: payload["series"][0].update({"fact_warning_count": "1"})),
            ("dropped_unsupported_count", lambda payload: payload["series"][0].update({"dropped_unsupported_count": -1})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_validation_warnings_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "validation_warnings.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "validation_warnings.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_validation_warnings" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_signal_quality_root_shape(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("ic_decay", []),
            ("rolling_ic", []),
            ("kelly", []),
            ("turnover", []),
            ("error", 42),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_signal_quality_payload()
                if field == "error":
                    payload = {"schema_version": 1, "error": bad_value}
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "signal_quality.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "signal_quality.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_signal_quality" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_signal_quality_panel_values(self) -> None:
        cases = (
            ("sample_sizes", lambda payload: payload["ic_decay"]["sample_sizes"].update({"5d": "30"})),
            ("monotonic_decay", lambda payload: payload["ic_decay"]["factors"][0].update({"monotonic_decay": "true"})),
            ("latest_ic", lambda payload: payload["rolling_ic"]["factors"][0].update({"latest_ic": "0.22"})),
            ("series", lambda payload: payload["rolling_ic"]["factors"][0]["series"].append([])),
            ("haircut", lambda payload: payload["kelly"].update({"haircut": 1.2})),
            ("hit_rate", lambda payload: payload["kelly"]["by_direction"]["bull"].update({"hit_rate": 1.2})),
            ("kelly_half", lambda payload: payload["kelly"]["by_direction"]["bull"].update({"kelly_half": "0.275"})),
            ("avg_turnover", lambda payload: payload["turnover"].update({"avg_turnover": -0.1})),
            ("tickers", lambda payload: payload["turnover"]["points"][0].update({"tickers": -1})),
            ("turnover", lambda payload: payload["turnover"]["points"][0].update({"turnover": 1.2})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_signal_quality_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "signal_quality.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "signal_quality.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_signal_quality" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_analysis_quality_root_shape(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("runs", {}),
            ("latest", []),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_analysis_quality_payload()
                payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "analysis_quality.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "analysis_quality.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_analysis_quality" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_analysis_quality_run_values(self) -> None:
        cases = (
            ("run_date", lambda payload: payload["runs"][0].update({"run_date": ""})),
            ("success", lambda payload: payload["runs"][0].update({"success": "true"})),
            ("daily_api_cost_usd", lambda payload: payload["runs"][0].update({"daily_api_cost_usd": -0.01})),
            ("batch_count", lambda payload: payload["runs"][0].update({"batch_count": "4"})),
            ("validation_failure_count", lambda payload: payload["latest"].update({"validation_failure_count": -1})),
            ("hallucination_ratio", lambda payload: payload["latest"].update({"hallucination_ratio": 1.2})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_analysis_quality_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "analysis_quality.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "analysis_quality.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_analysis_quality" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_cost_log_root_shape(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("runs", {}),
            ("latest", []),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_cost_log_payload()
                payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "cost_log.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "cost_log.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_cost_log" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_cost_log_run_values(self) -> None:
        cases = (
            ("run_date", lambda payload: payload["runs"][0].update({"run_date": ""})),
            ("success", lambda payload: payload["runs"][0].update({"success": "true"})),
            ("total_cost_usd", lambda payload: payload["runs"][0].update({"total_cost_usd": -0.01})),
            ("profiles", lambda payload: payload["runs"][0].update({"profiles": []})),
            ("tokens", lambda payload: payload["runs"][0]["profiles"]["economy"].update({"tokens": "1000"})),
            ("cache_hit_ratio", lambda payload: payload["runs"][0]["profiles"]["economy"].update({"cache_hit_ratio": 1.2})),
            ("models", lambda payload: payload["runs"][0]["profiles"]["economy"].update({"models": {"gpt-5.4-mini": "1"}})),
            ("ensemble_enabled", lambda payload: payload["runs"][0]["routing"].update({"ensemble_enabled": "true"})),
            ("selected_count", lambda payload: payload["runs"][0]["routing"].update({"selected_count": -1})),
            ("budget_guard", lambda payload: payload["runs"][0].update({"budget_guard": []})),
            ("decision_counts", lambda payload: payload["runs"][0]["budget_guard"].update({"decision_counts": {"would_block": "1"}})),
            ("guarded_paths", lambda payload: payload["runs"][0]["budget_guard"].update({"guarded_paths": {"ensemble_deep": 1}})),
            ("total_estimated_incremental_cost_usd", lambda payload: payload["runs"][0]["budget_guard"].update({"total_estimated_incremental_cost_usd": -0.01})),
            ("selected_ticker_count", lambda payload: payload["latest"]["deep_pass_value"].update({"selected_ticker_count": "3"})),
            ("share_of_total_cost", lambda payload: payload["latest"]["deep_pass_value"].update({"share_of_total_cost": 1.2})),
            ("worth_it_hint", lambda payload: payload["latest"]["deep_pass_value"].update({"worth_it_hint": ""})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_cost_log_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "cost_log.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "cost_log.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_cost_log" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_backtest_summary_root_shape(self) -> None:
        cases = (
            ("status", None),
            ("status", "broken"),
            ("signals", -1),
            ("signals", "2"),
            ("pending_signals", -1),
            ("strategy", None),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_backtest_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "backtest_summary.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "backtest_summary.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_backtest_summary" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_backtest_summary_nested_values(self) -> None:
        cases = (
            ("bull.signals", lambda payload: payload["bull"].update({"signals": "1"})),
            ("equity_curve.equity_multiple", lambda payload: payload["equity_curve"][0].update({"equity_multiple": "1.03"})),
            ("equity_curve.date", lambda payload: payload["equity_curve"][0].update({"date": None})),
            ("ticker_rows.signals", lambda payload: payload["ticker_rows"][0].update({"signals": -1})),
            ("ticker_rows.avg_return", lambda payload: payload["ticker_rows"][0].update({"avg_return": None})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_backtest_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "backtest_summary.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "backtest_summary.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_backtest_summary" and field.split(".")[-1] in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_monthly_summary_root_shape(self) -> None:
        cases = (
            ("month", None),
            ("status", None),
            ("status", "broken"),
            ("trading_days", -1),
            ("trading_days", "3"),
            ("start_date", None),
            ("top_tickers", {}),
            ("top_sectors", {}),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_monthly_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "monthly_summary.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "monthly_summary.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_monthly_summary" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_monthly_summary_rows(self) -> None:
        cases = (
            ("top_tickers.ticker", lambda payload: payload["top_tickers"][0].update({"ticker": None})),
            ("top_tickers.avg_daily_change", lambda payload: payload["top_tickers"][0].update({"avg_daily_change": None})),
            ("top_sectors.sector", lambda payload: payload["top_sectors"][0].update({"sector": None})),
            ("top_sectors.avg_daily_change", lambda payload: payload["top_sectors"][0].update({"avg_daily_change": None})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_monthly_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "monthly_summary.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "monthly_summary.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_monthly_summary" and field.split(".")[-1] in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_routing_outcome_root_and_summary_shape(self) -> None:
        cases = (
            ("run_count", -1),
            ("run_count", "1"),
            ("evaluated_signals", -1),
            ("status", "broken"),
            ("summary", []),
            ("periods", {}),
            ("deep_selected_count", lambda payload: payload["summary"].update({"deep_selected_count": -1})),
            ("deep_selected_avg_return_20d", lambda payload: payload["summary"].update({"deep_selected_avg_return_20d": "4.0"})),
            ("period", lambda payload: payload["periods"][0].update({"period": None})),
            ("economy_only_count", lambda payload: payload["periods"][0].update({"economy_only_count": "1"})),
        )
        for field, bad_value in cases:
            with self.subTest(field=field):
                payload = _valid_routing_outcome_payload()
                if callable(bad_value):
                    bad_value(payload)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "routing_outcome.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "routing_outcome.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_routing_outcome" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_routing_outcome_latest_run_shape(self) -> None:
        cases = (
            ("trigger_range", lambda payload: payload["latest_run"].update({"trigger_range": [25]})),
            ("max_daily_ensemble", lambda payload: payload["latest_run"].update({"max_daily_ensemble": "3"})),
            ("portfolio_priority", lambda payload: payload["latest_run"].update({"portfolio_priority": "true"})),
            ("selected_tickers", lambda payload: payload["latest_run"].update({"selected_tickers": ["AAPL", None]})),
            ("selected_count", lambda payload: payload["latest_run"]["router_budget_estimate"].update({"selected_count": -1})),
            ("estimated_monthly_cost_usd", lambda payload: payload["latest_run"]["router_budget_estimate"].update({"estimated_monthly_cost_usd": "0.44"})),
            ("ticker", lambda payload: payload["latest_run"]["tickers"][0].update({"ticker": None})),
            ("selected_for_deep", lambda payload: payload["latest_run"]["tickers"][0].update({"selected_for_deep": "true"})),
            ("router_priority_score", lambda payload: payload["latest_run"]["tickers"][0].update({"router_priority_score": "27.5"})),
            ("router_reason_codes", lambda payload: payload["latest_run"]["tickers"][0].update({"router_reason_codes": ["ok", None]})),
            ("skipped_due_to_priority", lambda payload: payload["latest_run"]["tickers"][0].update({"skipped_due_to_priority": "false"})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_routing_outcome_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "routing_outcome.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "routing_outcome.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_routing_outcome" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_performance_baseline_shape_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "performance_baseline.json", {"schema_version": 1})
            _write_json(
                root / "web" / "public" / "output" / "data" / "performance_baseline.json",
                {"schema_version": 1},
            )

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("invalid_performance_baseline", {issue.code for issue in result.issues})

    def test_detects_performance_baseline_missing_evidence_cache_fields(self) -> None:
        baseline = _valid_performance_baseline_payload()
        baseline["evidence"] = {
            "coverage_ratio": 0.0,
            "priority_coverage_ratio": 0.0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "performance_baseline.json", baseline)
            _write_json(root / "web" / "public" / "output" / "data" / "performance_baseline.json", baseline)

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                issue.code == "invalid_performance_baseline"
                and "evidence cache" in issue.detail
                for issue in result.issues
            )
        )

    def test_detects_invalid_performance_baseline_root_values(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("as_of", None),
            ("status", None),
            ("latest_run_date", None),
            ("monthly_budget_usd", -1.0),
            ("monthly_budget_usd", "10.0"),
            ("cost", []),
            ("quality", []),
            ("signals", []),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_performance_baseline_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "performance_baseline.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "performance_baseline.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_performance_baseline" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_performance_baseline_cost_quality_signal_values(self) -> None:
        cases = (
            ("total_cost_usd", lambda payload: payload["cost"].update({"total_cost_usd": -0.01})),
            ("estimated_monthly_cost_usd", lambda payload: payload["cost"].update({"estimated_monthly_cost_usd": "9.5"})),
            ("budget_usage_ratio", lambda payload: payload["cost"].update({"budget_usage_ratio": -0.1})),
            ("llm_calls", lambda payload: payload["cost"].update({"llm_calls": "179"})),
            ("ticker_count_for_rate", lambda payload: payload["cost"].update({"ticker_count_for_rate": -1})),
            ("llm_calls_per_ticker", lambda payload: payload["cost"].update({"llm_calls_per_ticker": -0.1})),
            ("deep_selected_count", lambda payload: payload["cost"].update({"deep_selected_count": -1})),
            ("routing_conflicted_count", lambda payload: payload["cost"].update({"routing_conflicted_count": -1})),
            ("budget_guard_would_block_count", lambda payload: payload["cost"].update({"budget_guard_would_block_count": -1})),
            ("budget_guard_blocked_count", lambda payload: payload["cost"].update({"budget_guard_blocked_count": -1})),
            ("validated_ticker_count", lambda payload: payload["quality"].update({"validated_ticker_count": "283"})),
            ("validation_failure_count", lambda payload: payload["quality"].update({"validation_failure_count": -1})),
            ("validation_failure_rate", lambda payload: payload["quality"].update({"validation_failure_rate": 1.2})),
            ("hallucination_warning_count", lambda payload: payload["quality"].update({"hallucination_warning_count": -1})),
            ("hallucination_ratio", lambda payload: payload["quality"].update({"hallucination_ratio": 1.2})),
            ("fact_warning_count", lambda payload: payload["quality"].update({"fact_warning_count": -1})),
            ("consistency_warning_count", lambda payload: payload["quality"].update({"consistency_warning_count": "0"})),
            ("turnover_status", lambda payload: payload["signals"].update({"turnover_status": None})),
            ("avg_turnover", lambda payload: payload["signals"].update({"avg_turnover": -0.1})),
            ("kelly_status", lambda payload: payload["signals"].update({"kelly_status": None})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_performance_baseline_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "performance_baseline.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "performance_baseline.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_performance_baseline" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_performance_baseline_evidence_values(self) -> None:
        cases = (
            ("provider", lambda payload: payload["evidence"].update({"provider": None})),
            ("ticker_count", lambda payload: payload["evidence"].update({"ticker_count": "23"})),
            ("covered_ticker_count", lambda payload: payload["evidence"].update({"covered_ticker_count": -1})),
            ("coverage_ratio", lambda payload: payload["evidence"].update({"coverage_ratio": 1.2})),
            ("average_coverage_score", lambda payload: payload["evidence"].update({"average_coverage_score": -0.1})),
            ("average_freshness_score", lambda payload: payload["evidence"].update({"average_freshness_score": 1.2})),
            ("candidate_ticker_count", lambda payload: payload["evidence"].update({"candidate_ticker_count": -1})),
            ("searched_ticker_count", lambda payload: payload["evidence"].update({"searched_ticker_count": "0"})),
            ("cache_ttl_hours", lambda payload: payload["evidence"].update({"cache_ttl_hours": -1})),
            ("cache_hit_count", lambda payload: payload["evidence"].update({"cache_hit_count": -1})),
            ("stale_cache_hit_count", lambda payload: payload["evidence"].update({"stale_cache_hit_count": -1})),
            ("cache_hit_ratio", lambda payload: payload["evidence"].update({"cache_hit_ratio": 1.2})),
            ("stale_cache_hit_ratio", lambda payload: payload["evidence"].update({"stale_cache_hit_ratio": -0.1})),
            ("average_cache_age_hours", lambda payload: payload["evidence"].update({"average_cache_age_hours": -0.1})),
            ("max_cache_age_hours", lambda payload: payload["evidence"].update({"max_cache_age_hours": "24"})),
            ("provider_candidate_count", lambda payload: payload["evidence"].update({"provider_candidate_count": -1})),
            ("status_counts", lambda payload: payload["evidence"].update({"status_counts": {"covered": "2"}})),
            ("priority_ticker_count", lambda payload: payload["evidence"].update({"priority_ticker_count": -1})),
            ("priority_covered_ticker_count", lambda payload: payload["evidence"].update({"priority_covered_ticker_count": "1"})),
            ("priority_coverage_ratio", lambda payload: payload["evidence"].update({"priority_coverage_ratio": 1.2})),
            ("priority_status_counts", lambda payload: payload["evidence"].update({"priority_status_counts": {"covered": -1}})),
            (
                "priority_refresh_reasons",
                lambda payload: payload["evidence"].update({"priority_refresh_reasons": {"router_selected": "2"}}),
            ),
            (
                "priority_refresh_candidate_count",
                lambda payload: payload["evidence"].update({"priority_refresh_candidate_count": -1}),
            ),
            (
                "priority_provider_error_count",
                lambda payload: payload["evidence"].update({"priority_provider_error_count": "0"}),
            ),
            (
                "priority_not_refreshed_count",
                lambda payload: payload["evidence"].update({"priority_not_refreshed_count": -1}),
            ),
            (
                "priority_no_evidence_count",
                lambda payload: payload["evidence"].update({"priority_no_evidence_count": -1}),
            ),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_performance_baseline_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "performance_baseline.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "performance_baseline.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_performance_baseline" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_performance_baseline_p1_readiness_values(self) -> None:
        cases = (
            ("p1_readiness", lambda payload: payload.update({"p1_readiness": []})),
            ("status", lambda payload: payload["p1_readiness"].update({"status": ""})),
            ("mode", lambda payload: payload["p1_readiness"].update({"mode": []})),
            ("tracks", lambda payload: payload["p1_readiness"].update({"tracks": {}})),
            (
                "search_evidence_provider",
                lambda payload: payload["p1_readiness"]["tracks"].pop(
                    "search_evidence_provider"
                ),
            ),
            (
                "candidate_ticker_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"candidate_ticker_count": -1}),
            ),
            (
                "provider_call_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"provider_call_count": -1}),
            ),
            (
                "cache_error_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"cache_error_count": -1}),
            ),
            (
                "skipped_ticker_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"skipped_ticker_count": -1}),
            ),
            (
                "cap_review_status",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"cap_review_status": ""}),
            ),
            (
                "priority_refresh_candidate_ratio",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"priority_refresh_candidate_ratio": 1.2}),
            ),
            (
                "provider_issue_status",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"provider_issue_status": ""}),
            ),
            (
                "operational_issue_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"operational_issue_count": -1}),
            ),
            (
                "stale_cache_reuse_status",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"stale_cache_reuse_status": ""}),
            ),
            (
                "status_counts",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "search_evidence_provider"
                ].update({"status_counts": {"covered": "2"}}),
            ),
            (
                "enforce_review_status",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"enforce_review_status": ""}
                ),
            ),
            (
                "decision_counts",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"decision_counts": {"would_block": "6"}}
                ),
            ),
            (
                "guarded_path_status_counts",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"guarded_path_status_counts": {"would_block": "2"}}
                ),
            ),
            (
                "would_block_count",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"would_block_count": -1}
                ),
            ),
            (
                "would_block_path_count",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"would_block_path_count": -1}
                ),
            ),
            (
                "blocked_path_count",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"blocked_path_count": -1}
                ),
            ),
            (
                "allow_path_count",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"allow_path_count": -1}
                ),
            ),
            (
                "blocked_count",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"blocked_count": -1}
                ),
            ),
            (
                "total_estimated_incremental_cost_usd",
                lambda payload: payload["p1_readiness"]["tracks"]["budget_guard"].update(
                    {"total_estimated_incremental_cost_usd": "0.12"}
                ),
            ),
            (
                "completed_return_windows",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"completed_return_windows": [None]}),
            ),
            (
                "completed_return_window_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"completed_return_window_count": -1}),
            ),
            (
                "evaluated_signal_window_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"evaluated_signal_window_count": -1}),
            ),
            (
                "conviction_bucket_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"conviction_bucket_count": -1}),
            ),
            (
                "populated_conviction_bucket_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"populated_conviction_bucket_count": -1}),
            ),
            (
                "calibration_status",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"calibration_status": ""}),
            ),
            (
                "regime_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"regime_count": -1}),
            ),
            (
                "factor_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"factor_count": -1}),
            ),
            (
                "factor_attribution_status",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"factor_attribution_status": ""}),
            ),
            (
                "missing_factor_sample_count",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"missing_factor_sample_count": -1}),
            ),
            (
                "action_change_coverage_ratio",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"action_change_coverage_ratio": 1.2}),
            ),
            (
                "loop_readiness_status",
                lambda payload: payload["p1_readiness"]["tracks"][
                    "analysis_performance"
                ].update({"loop_readiness_status": ""}),
            ),
            (
                "invalid_json_count",
                lambda payload: payload["p1_readiness"]["tracks"]["output_schema"].update(
                    {"invalid_json_count": -1}
                ),
            ),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_performance_baseline_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "performance_baseline.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "performance_baseline.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_performance_baseline" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_performance_trends_shape_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "output" / "data" / "performance_trends.json", {"schema_version": 1})
            _write_json(
                root / "web" / "public" / "output" / "data" / "performance_trends.json",
                {"schema_version": 1},
            )

            result = check_output_health(root)

        self.assertFalse(result.ok)
        self.assertIn("invalid_performance_trends", {issue.code for issue in result.issues})

    def test_detects_invalid_performance_trends_root_values(self) -> None:
        cases = (
            ("schema_version", -1),
            ("schema_version", "1"),
            ("as_of", None),
            ("monthly_budget_usd", -1.0),
            ("monthly_budget_usd", "10.0"),
            ("runs", {}),
        )
        for field, bad_value in cases:
            with self.subTest(field=field, bad_value=bad_value):
                payload = _valid_performance_trends_payload()
                if bad_value is None:
                    payload.pop(field)
                else:
                    payload[field] = bad_value
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "performance_trends.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "performance_trends.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_performance_trends" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_detects_invalid_performance_trends_run_values(self) -> None:
        cases = (
            ("run_date", lambda payload: payload["runs"][0].update({"run_date": ""})),
            ("success", lambda payload: payload["runs"][0].update({"success": "true"})),
            ("total_cost_usd", lambda payload: payload["runs"][0].update({"total_cost_usd": -0.01})),
            ("llm_calls", lambda payload: payload["runs"][0].update({"llm_calls": "179"})),
            ("hallucination_ratio", lambda payload: payload["runs"][0].update({"hallucination_ratio": 1.2})),
            ("validation_failure_count", lambda payload: payload["runs"][0].update({"validation_failure_count": -1})),
            ("deep_selected_count", lambda payload: payload["runs"][0].update({"deep_selected_count": -1})),
            ("budget_guard_would_block_count", lambda payload: payload["runs"][0].update({"budget_guard_would_block_count": -1})),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                payload = _valid_performance_trends_payload()
                mutate(payload)
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    _write_json(root / "output" / "data" / "performance_trends.json", payload)
                    _write_json(root / "web" / "public" / "output" / "data" / "performance_trends.json", payload)

                    result = check_output_health(root)

                self.assertFalse(result.ok)
                self.assertTrue(
                    any(
                        issue.code == "invalid_performance_trends" and field in issue.detail
                        for issue in result.issues
                    )
                )

    def test_cli_returns_nonzero_when_health_check_fails(self) -> None:
        from src.cli.output_health_check import main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "data"
            mirror = root / "web" / "public" / "output" / "data"
            source.mkdir(parents=True)
            mirror.mkdir(parents=True)
            (source / "index.json").write_text('{"schema_version": ', encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["--project-root", str(root)])

        self.assertEqual(exit_code, 1)
        self.assertIn("invalid_json", stdout.getvalue())
