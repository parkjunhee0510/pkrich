from __future__ import annotations

import json
import os
from typing import Any

from src.analyzer.base import AnalysisContext, ModuleResult, StructuredLLMModule
from src.analyzer.prompts import PromptContext, PromptTemplate, get_prompt_template
from src.analyzer.validator import ResponseValidator
from src.utils.cost_tracker import calculate_response_cost
from src.utils.model_config import safe_input_token_budget
from src.utils.pipeline_logging import record_pipeline_event
from src.utils.token_estimator import estimate_batch_tokens


def run_structured_llm_module(
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    *,
    prompt_template_override: PromptTemplate | None = None,
    capture_validation_details: bool = False,
) -> ModuleResult:
    if not os.getenv("OPENAI_API_KEY") or ctx.model_profile is None:
        return _build_fallback_result(module, ctx, reason="missing_openai_key")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception:
        return _build_fallback_result(module, ctx, reason="openai_client_failed")

    tickers = [item.ticker for item in ctx.watchlist]
    all_results: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {"batch_count": 0, "fallback_batches": 0}
    if capture_validation_details:
        diagnostics["validation_details"] = {}
    validator = ResponseValidator()
    prompt_template = prompt_template_override or get_prompt_template(
        getattr(ctx.model_profile, "prompt_version", "research_v1"),
        module.name,
    )
    prompt_context = PromptContext(
        run_date=ctx.run_date,
        macro_context=ctx.macro_context,
        account_size_hint=ctx.portfolio_account_size,
        model_profile=ctx.model_profile,
        metadata={"module_name": module.name},
    )
    for batch_tickers in _split_batches(module, ctx, tickers):
        diagnostics["batch_count"] += 1
        batch_payload = module.build_batch_payload(ctx, batch_tickers)
        try:
            response = client.responses.create(
                model=ctx.model_profile.model,
                max_output_tokens=ctx.model_profile.max_output_tokens,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": prompt_template.render_system(prompt_context)}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt_template.render_user(batch_payload, prompt_context)}],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": f"{prompt_template.version}_{prompt_template.name}",
                        "schema": prompt_template.output_schema,
                        "strict": True,
                    }
                },
            )
            usage_cost = calculate_response_cost(response, ctx.model_profile)
            record_pipeline_event(
                "analyzer",
                "info",
                "openai_usage_recorded",
                model=ctx.model_profile.model,
                model_profile=ctx.model_profile.name,
                module=module.name,
                input_tokens=usage_cost.input_tokens,
                output_tokens=usage_cost.output_tokens,
                cached_input_tokens=usage_cost.cached_input_tokens,
                total_tokens=usage_cost.total_tokens,
                estimated_cost_usd=usage_cost.estimated_cost_usd,
            )
            response_text = getattr(response, "output_text", "").strip()
            prompt_template.validate_response(json.loads(response_text))
            parsed = module.parse_batch_response(response_text, batch_tickers, ctx)
            record_pipeline_event(
                "analyzer",
                "info",
                "openai_response_validated",
                module=module.name,
                ticker_count=len(batch_tickers),
            )
            for ticker in batch_tickers:
                validated = validator.validate(
                    parsed.get(ticker, {}),
                    _result_schema_for_ticker(module, ticker, ctx),
                    {
                        "raw_payload": ctx.raw_payload_by_ticker.get(ticker, {}),
                        "fallback": module.fallback_for_ticker(ticker, ctx),
                        "intermediate": ctx.intermediate_results.get(ticker, {}),
                    },
                )
                if validated.warnings:
                    counts = validated.counts
                    record_pipeline_event(
                        "analyzer",
                        "warning",
                        "openai_response_validation_failed",
                        module=module.name,
                        ticker=ticker,
                        warning_count=len(validated.warnings),
                        warning_fields=",".join(sorted({warning.field for warning in validated.warnings})),
                        warning_categories=",".join(sorted(counts.keys())),
                        schema_violation_count=counts.get("schema_violation", 0),
                        fact_warning_count=counts.get("fact_warning", 0),
                        consistency_warning_count=counts.get("consistency_warning", 0),
                        hallucination_warning_count=counts.get("hallucination_warning", 0),
                        dropped_unsupported_count=counts.get("dropped_unsupported", 0),
                    )
                if capture_validation_details:
                    diagnostics["validation_details"][ticker] = {
                        "warning_count": len(validated.warnings),
                        "counts": validated.counts,
                        "warnings": [
                            {
                                "category": warning.category,
                                "field": warning.field,
                                "message": warning.message,
                            }
                            for warning in validated.warnings
                        ],
                    }
                all_results[ticker] = validated.sanitized_response
        except Exception as exc:
            diagnostics["fallback_batches"] += 1
            record_pipeline_event(
                "analyzer",
                "warning",
                "openai_response_validation_failed",
                module=module.name,
                ticker_count=len(batch_tickers),
                error_type=type(exc).__name__,
                error_message=str(exc),
                schema_violation_count=len(batch_tickers),
            )
            for ticker in batch_tickers:
                all_results[ticker] = module.fallback_for_ticker(ticker, ctx)
                if capture_validation_details:
                    diagnostics["validation_details"][ticker] = {
                        "warning_count": 1,
                        "counts": {"schema_violation": 1},
                        "warnings": [
                            {
                                "category": "schema_violation",
                                "field": "*",
                                "message": f"{type(exc).__name__}: {exc}",
                            }
                        ],
                    }

    return ModuleResult(results_by_ticker=all_results, diagnostics=diagnostics)


def _split_batches(
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    tickers: list[str],
) -> list[list[str]]:
    token_budget = safe_input_token_budget(ctx.model_profile)
    batches: list[list[str]] = []
    current: list[str] = []
    for ticker in tickers:
        candidate = current + [ticker]
        payload = module.build_batch_payload(ctx, candidate)
        should_split = current and estimate_batch_tokens(payload) > token_budget
        if should_split:
            batches.append(current)
            current = [ticker]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


def _build_fallback_result(
    module: StructuredLLMModule,
    ctx: AnalysisContext,
    *,
    reason: str,
) -> ModuleResult:
    return ModuleResult(
        results_by_ticker={
            item.ticker: module.fallback_for_ticker(item.ticker, ctx)
            for item in ctx.watchlist
        },
        diagnostics={"fallback_reason": reason},
    )


def parse_ticker_batch(content: str, expected_tickers: list[str]) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    tickers = parsed.get("tickers")
    if not isinstance(tickers, list):
        raise ValueError("Response missing tickers array")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    expected = set(expected_tickers)
    for entry in tickers:
        if not isinstance(entry, dict):
            raise ValueError("Ticker entry must be an object")
        ticker = str(entry.get("ticker", "")).strip().upper()
        if ticker not in expected:
            raise ValueError(f"Unexpected ticker in response: {ticker}")
        if ticker in seen:
            raise ValueError(f"Duplicate ticker in response: {ticker}")
        seen.add(ticker)
        validated.append(entry)
    missing = expected - seen
    if missing:
        raise ValueError(f"Missing tickers in response: {', '.join(sorted(missing))}")
    return validated


def _result_schema_for_ticker(module: StructuredLLMModule, ticker: str, ctx: AnalysisContext) -> dict[str, str]:
    fallback = ctx.fallback_payload_by_ticker.get(ticker, {})
    schema: dict[str, str] = {}
    for key in module.produces:
        value = fallback.get(key)
        if isinstance(value, str):
            schema[key] = "string"
        elif isinstance(value, list):
            schema[key] = "list"
        elif isinstance(value, dict):
            schema[key] = "dict"
    return schema
