from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.analyzer.base import AnalysisContext, AnalysisModule, ModuleResult


@dataclass(frozen=True)
class RunnerResult:
    results_by_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def run_analysis_modules(
    ctx: AnalysisContext,
    modules: list[AnalysisModule],
) -> RunnerResult:
    merged: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {"executed_modules": [], "skipped_modules": []}
    available_inputs = set(ctx.available_inputs)

    for module in modules:
        missing = sorted(module.requires - available_inputs)
        if missing:
            diagnostics["skipped_modules"].append(
                {
                    "module": module.name,
                    "reason": "missing_requires",
                    "missing": missing,
                }
            )
            continue

        result = module.analyze(ctx)
        diagnostics["executed_modules"].append(module.name)
        if result.diagnostics:
            diagnostics[module.name] = result.diagnostics
        for ticker, payload in result.results_by_ticker.items():
            ticker_payload = merged.setdefault(ticker, {})
            ticker_payload.update(payload)
        available_inputs.update(module.produces)

    return RunnerResult(results_by_ticker=merged, diagnostics=diagnostics)

