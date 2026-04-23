from __future__ import annotations

from typing import Any


def build_quality_summary(
    module_diagnostics: dict[str, Any] | None,
    *,
    tickers: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    diagnostics = module_diagnostics or {}
    validation_details = diagnostics.get("validation_details", {})
    fallback_used = bool(
        diagnostics.get("fallback_used", False)
        or diagnostics.get("fallback_reason")
        or diagnostics.get("fallback_batches", 0)
    )
    if not isinstance(validation_details, dict):
        validation_details = {}

    quality_summary_by_ticker: dict[str, dict[str, Any]] = {}
    for ticker, details in validation_details.items():
        if not isinstance(details, dict):
            continue
        counts = details.get("counts", {})
        warnings = details.get("warnings", [])
        summary: dict[str, Any] = {
            "fact_warning_count": _coerce_int((counts or {}).get("fact_warning")),
            "hallucination_warning_count": _coerce_int((counts or {}).get("hallucination_warning")),
            "consistency_warning_count": _coerce_int((counts or {}).get("consistency_warning")),
            "fallback_used": fallback_used,
            "encoding_issue_detected": _detect_encoding_issue(warnings),
        }
        if "missing_critical_fields" in details:
            summary["missing_critical_fields"] = _coerce_int(details.get("missing_critical_fields"))
        if "critical_field_total" in details:
            summary["critical_field_total"] = _coerce_int(details.get("critical_field_total"))
        quality_summary_by_ticker[str(ticker)] = summary

    if quality_summary_by_ticker or not fallback_used:
        return quality_summary_by_ticker

    for ticker in tickers or []:
        quality_summary_by_ticker[str(ticker)] = {
            "fact_warning_count": 0,
            "hallucination_warning_count": 0,
            "consistency_warning_count": 0,
            "fallback_used": True,
            "encoding_issue_detected": False,
        }
    return quality_summary_by_ticker


def merge_quality_summary_maps(*summary_maps: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for summary_map in summary_maps:
        if not isinstance(summary_map, dict):
            continue
        for ticker, summary in summary_map.items():
            if not isinstance(summary, dict):
                continue
            existing = merged.setdefault(str(ticker), {})
            for key in (
                "fact_warning_count",
                "hallucination_warning_count",
                "consistency_warning_count",
                "missing_critical_fields",
                "critical_field_total",
            ):
                if key in summary:
                    existing[key] = _coerce_int(existing.get(key)) + _coerce_int(summary.get(key))
            for key in ("fallback_used", "encoding_issue_detected"):
                if key in summary:
                    existing[key] = bool(existing.get(key, False) or summary.get(key, False))
    return merged


def select_quality_summary_by_source(
    *,
    tickers: list[str],
    economy_summary_by_ticker: dict[str, dict[str, Any]] | None = None,
    deep_summary_by_ticker: dict[str, dict[str, Any]] | None = None,
    tie_break_summary_by_ticker: dict[str, dict[str, Any]] | None = None,
    selected_source_by_ticker: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    economy_summary_by_ticker = economy_summary_by_ticker or {}
    deep_summary_by_ticker = deep_summary_by_ticker or {}
    tie_break_summary_by_ticker = tie_break_summary_by_ticker or {}
    selected_source_by_ticker = selected_source_by_ticker or {}

    summary_by_source = {
        "economy": economy_summary_by_ticker,
        "deep": deep_summary_by_ticker,
        "tie_break": tie_break_summary_by_ticker,
    }
    selected_summary_by_ticker: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        source = str(selected_source_by_ticker.get(ticker, "economy"))
        summary = summary_by_source.get(source, {}).get(ticker)
        if isinstance(summary, dict):
            selected_summary_by_ticker[ticker] = dict(summary)
    return selected_summary_by_ticker


def _detect_encoding_issue(warnings: Any) -> bool:
    if not isinstance(warnings, list):
        return False
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        message = str(warning.get("message", "")).lower()
        field = str(warning.get("field", "")).lower()
        if "encoding" in message or "encoding" in field or "\ufffd" in message or "replacement char" in message:
            return True
    return False


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
