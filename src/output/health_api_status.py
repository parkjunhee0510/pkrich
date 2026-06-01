"""Health checks for API status output artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.output.health_common import (
    OutputHealthIssue,
    _is_non_negative_int,
    _is_non_negative_int_mapping,
    _is_non_negative_number,
    _is_probability,
    _load_json_object,
)


_API_PROVIDERS = ("yfinance", "alpha_vantage", "polygon", "fmp", "finnhub", "sec_edgar", "ir_rss")
_API_PROVIDER_STATUSES = {"active", "partial", "limited", "failing", "idle"}
_API_PROVIDER_STATES = {"used", "failed", "throttled", "unavailable", "not_used"}


def _validate_api_status_artifacts(root: Path) -> Iterable[OutputHealthIssue]:
    if not root.exists():
        return ()

    issues: list[OutputHealthIssue] = []
    status_path = root / "api_status.json"
    if status_path.exists():
        payload = _load_json_object(status_path)
        issue = _validate_api_status_payload(status_path, payload)
        if issue is not None:
            issues.append(issue)

    matrix_path = root / "api_ticker_matrix.json"
    if matrix_path.exists():
        try:
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        except Exception:
            matrix = None
        issue = _validate_api_ticker_matrix_payload(matrix_path, matrix)
        if issue is not None:
            issues.append(issue)

    return tuple(issues)


def _validate_api_status_payload(path: Path, payload: dict) -> OutputHealthIssue | None:
    required = {"schema_version", "run_date", "log_path", "pipeline_completed", "providers", "llm"}
    if not required.issubset(payload.keys()):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "missing one of schema_version/run_date/log_path/pipeline_completed/providers/llm",
        )
    if not _is_non_negative_int(payload.get("schema_version")):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "schema_version must be a non-negative integer",
        )
    for field in ("run_date", "log_path"):
        if not isinstance(payload.get(field), str) or not payload.get(field, "").strip():
            return OutputHealthIssue(
                "invalid_api_status",
                str(path),
                f"{field} must be a non-empty string",
            )
    if not isinstance(payload.get("pipeline_completed"), bool):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "pipeline_completed must be a boolean",
        )

    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "providers must be an object",
        )
    missing = [provider for provider in _API_PROVIDERS if provider not in providers]
    if missing:
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            f"providers missing {', '.join(missing)}",
        )
    for provider in _API_PROVIDERS:
        issue = _validate_api_provider_summary(path, provider, providers.get(provider))
        if issue is not None:
            return issue

    issue = _validate_api_llm_summary(path, payload.get("llm"))
    if issue is not None:
        return issue
    return None


def _validate_api_provider_summary(path: Path, provider: str, summary: object) -> OutputHealthIssue | None:
    count_fields = (
        "used_tickers",
        "throttled_tickers",
        "unavailable_tickers",
        "failed_tickers",
        "not_used_tickers",
    )
    required = {"overall_status", *count_fields}
    if not isinstance(summary, dict) or not required.issubset(summary.keys()):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            f"providers {provider} missing overall_status/count fields",
        )
    if summary.get("overall_status") not in _API_PROVIDER_STATUSES:
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            f"overall_status must be one of active/partial/limited/failing/idle for provider {provider}",
        )
    for field in count_fields:
        if not _is_non_negative_int(summary.get(field)):
            return OutputHealthIssue(
                "invalid_api_status",
                str(path),
                f"{field} must be a non-negative integer for provider {provider}",
            )
    return None


def _validate_api_llm_summary(path: Path, llm: object) -> OutputHealthIssue | None:
    count_fields = (
        "planned_batches",
        "completed_batches",
        "failed_batches",
        "validation_failures",
    )
    required = {"used", "estimated_cost_usd", "latest_model", "models_used", "quality", *count_fields}
    if not isinstance(llm, dict) or not required.issubset(llm.keys()):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "llm missing used/batch/cost/model/quality fields",
        )
    if not isinstance(llm.get("used"), bool):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "used must be a boolean for llm",
        )
    for field in count_fields:
        if not _is_non_negative_int(llm.get(field)):
            return OutputHealthIssue(
                "invalid_api_status",
                str(path),
                f"{field} must be a non-negative integer for llm",
            )
    if not _is_non_negative_number(llm.get("estimated_cost_usd")):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "estimated_cost_usd must be a non-negative number for llm",
        )
    if not isinstance(llm.get("latest_model"), str):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "latest_model must be a string for llm",
        )
    if not _is_non_negative_int_mapping(llm.get("models_used")):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "models_used must be an object with non-negative integer counts for llm",
        )
    quality = llm.get("quality")
    if not isinstance(quality, dict):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "quality must be an object for llm",
        )
    issue = _validate_api_llm_quality(path, quality)
    if issue is not None:
        return issue
    return None


def _validate_api_llm_quality(path: Path, quality: dict) -> OutputHealthIssue | None:
    if "run_date" in quality and not isinstance(quality.get("run_date"), str):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "run_date must be a string for llm quality",
        )
    if "success" in quality and not isinstance(quality.get("success"), bool):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "success must be a boolean for llm quality",
        )
    for field in (
        "batch_count",
        "validated_ticker_count",
        "validation_failure_count",
        "schema_violation_count",
        "fact_warning_count",
        "consistency_warning_count",
        "hallucination_warning_count",
    ):
        if field in quality and not _is_non_negative_int(quality.get(field)):
            return OutputHealthIssue(
                "invalid_api_status",
                str(path),
                f"{field} must be a non-negative integer for llm quality",
            )
    if "daily_api_cost_usd" in quality and not _is_non_negative_number(quality.get("daily_api_cost_usd")):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "daily_api_cost_usd must be a non-negative number for llm quality",
        )
    if "hallucination_ratio" in quality and not _is_probability(quality.get("hallucination_ratio")):
        return OutputHealthIssue(
            "invalid_api_status",
            str(path),
            "hallucination_ratio must be a number from 0 to 1 for llm quality",
        )
    return None


def _validate_api_ticker_matrix_payload(path: Path, payload: object) -> OutputHealthIssue | None:
    if not isinstance(payload, list):
        return OutputHealthIssue(
            "invalid_api_ticker_matrix",
            str(path),
            "api_ticker_matrix must be a list",
        )
    required = {"ticker", "name", "sector", *_API_PROVIDERS}
    for index, row in enumerate(payload):
        if not isinstance(row, dict) or not required.issubset(row.keys()):
            return OutputHealthIssue(
                "invalid_api_ticker_matrix",
                str(path),
                f"api_ticker_matrix item {index} missing ticker/name/sector/provider state fields",
            )
        if not isinstance(row.get("ticker"), str) or not row.get("ticker", "").strip():
            return OutputHealthIssue(
                "invalid_api_ticker_matrix",
                str(path),
                f"ticker must be a non-empty string for api_ticker_matrix item {index}",
            )
        for field in ("name", "sector"):
            if not isinstance(row.get(field), str):
                return OutputHealthIssue(
                    "invalid_api_ticker_matrix",
                    str(path),
                    f"{field} must be a string for api_ticker_matrix item {index}",
                )
        for provider in _API_PROVIDERS:
            if row.get(provider) not in _API_PROVIDER_STATES:
                return OutputHealthIssue(
                    "invalid_api_ticker_matrix",
                    str(path),
                    f"{provider} must be one of used/failed/throttled/unavailable/not_used for api_ticker_matrix item {index}",
                )
    return None
