from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from src.analyzer.base import AnalysisContext, ModuleResult
from src.analyzer.llm_runtime import run_structured_llm_module
from src.analyzer.modules.signal_takeaway_module import SignalTakeawayModule
from src.analyzer.payloads import build_fallback_payloads, build_raw_payloads
from src.analyzer.prompts import PromptTemplate
from src.types import CollectedTickerData, NewsItem, TickerAnalysis, WatchlistItem
from src.utils.model_config import ModelProfile, load_model_profile
from src.utils.signal_tracker import load_signal_rows

_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_BULLISH_TERMS = ("매수", "상승", "강세", "bull")
_BEARISH_TERMS = ("매도", "하락", "약세", "bear")


@dataclass(frozen=True)
class ABTestRunner:
    run_date: date
    watchlist: list[WatchlistItem]
    collected: dict[str, CollectedTickerData]
    news_map: dict[str, list[NewsItem]]
    analyses: list[TickerAnalysis]
    model_profile: ModelProfile | None = None
    output_root: Path | None = None
    signal_csv_path: Path | None = None
    variant_executor: Callable[[SignalTakeawayModule, AnalysisContext, PromptTemplate], ModuleResult] | None = None

    def select_weekly_sample(self, *, sample_size: int = 5) -> list[str]:
        tickers = [item.ticker for item in self.watchlist if item.ticker in self.collected]
        if len(tickers) <= sample_size:
            return tickers
        iso_year, iso_week, _ = self.run_date.isocalendar()
        seeded_random = random.Random(f"{iso_year}-W{iso_week}-ab-test")
        return sorted(seeded_random.sample(tickers, sample_size))

    def run_test(
        self,
        tickers: list[str],
        variant_a: PromptTemplate,
        variant_b: PromptTemplate,
    ) -> dict[str, Any]:
        if not tickers:
            return {
                "status": "skipped",
                "reason": "no_tickers",
                "module": variant_a.name,
                "variant_a": _template_meta(variant_a),
                "variant_b": _template_meta(variant_b),
                "selected_tickers": [],
                "results": [],
                "summary": {},
            }

        subset_watchlist = [item for item in self.watchlist if item.ticker in set(tickers)]
        ctx = self._build_context(subset_watchlist)
        module = SignalTakeawayModule()
        result_a = self._execute_variant(module, ctx, variant_a)
        result_b = self._execute_variant(module, ctx, variant_b)

        signal_rows = load_signal_rows(self.signal_csv_path or ((self.output_root or Path("output")) / "data" / "signal_tracker.csv"))
        results: list[dict[str, Any]] = []
        for ticker in tickers:
            variant_a_payload = result_a.results_by_ticker.get(ticker, {})
            variant_b_payload = result_b.results_by_ticker.get(ticker, {})
            detail_a = _variant_detail(variant_a_payload, _validation_for_ticker(result_a, ticker), signal_rows, ticker)
            detail_b = _variant_detail(variant_b_payload, _validation_for_ticker(result_b, ticker), signal_rows, ticker)
            results.append(
                {
                    "ticker": ticker,
                    "variant_a": detail_a,
                    "variant_b": detail_b,
                    "preferred_variant": _preferred_variant(detail_a, detail_b),
                }
            )

        return {
            "status": "executed",
            "module": variant_a.name,
            "variant_a": _template_meta(variant_a),
            "variant_b": _template_meta(variant_b),
            "selected_tickers": tickers,
            "results": results,
            "summary": _build_summary(results),
        }

    def _build_context(self, subset_watchlist: list[WatchlistItem]) -> AnalysisContext:
        subset_collected = {item.ticker: self.collected[item.ticker] for item in subset_watchlist if item.ticker in self.collected}
        subset_news = {item.ticker: self.news_map.get(item.ticker, []) for item in subset_watchlist}
        raw_payloads = build_raw_payloads(subset_watchlist, subset_collected, subset_news)
        fallback_payloads = build_fallback_payloads(
            subset_watchlist,
            subset_collected,
            subset_news,
            self.run_date,
            raw_payload_by_ticker=raw_payloads,
            signal_history_map=None,
            account_size_hint=None,
        )
        analysis_by_ticker = {analysis.ticker: analysis for analysis in self.analyses}
        intermediate_results: dict[str, dict[str, Any]] = {}
        for item in subset_watchlist:
            analysis = analysis_by_ticker.get(item.ticker)
            if analysis is None:
                intermediate_results[item.ticker] = dict(fallback_payloads.get(item.ticker, {}))
                continue
            intermediate_results[item.ticker] = {
                "summary": analysis.summary,
                "trade_frame": analysis.trade_frame,
                "news_tone": analysis.news_tone,
                "risks_or_watchpoints": analysis.risks_or_watchpoints,
                "signal_or_takeaway": analysis.signal_or_takeaway,
            }

        return AnalysisContext(
            watchlist=subset_watchlist,
            collected=subset_collected,
            news_map=subset_news,
            run_date=self.run_date,
            model_profile=self.model_profile or load_model_profile(profile_name="economy"),
            raw_payload_by_ticker=raw_payloads,
            fallback_payload_by_ticker=fallback_payloads,
            intermediate_results=intermediate_results,
        )

    def _execute_variant(
        self,
        module: SignalTakeawayModule,
        ctx: AnalysisContext,
        prompt_template: PromptTemplate,
    ) -> ModuleResult:
        if self.variant_executor is not None:
            return self.variant_executor(module, ctx, prompt_template)
        return run_structured_llm_module(
            module,
            ctx,
            prompt_template_override=prompt_template,
            capture_validation_details=True,
        )


def build_weekly_ab_test_payload(
    *,
    run_date: date,
    watchlist: list[WatchlistItem],
    collected: dict[str, CollectedTickerData],
    news_map: dict[str, list[NewsItem]],
    analyses: list[TickerAnalysis],
    variant_a: PromptTemplate,
    variant_b: PromptTemplate,
    output_root: Path | None = None,
) -> dict[str, Any]:
    if run_date.weekday() != 6:
        return {
            "run_date": run_date.isoformat(),
            "status": "skipped",
            "reason": "not_sunday",
            "sample_size": 5,
            "module": variant_a.name,
            "variant_a": _template_meta(variant_a),
            "variant_b": _template_meta(variant_b),
            "selected_tickers": [],
            "results": [],
            "summary": {},
        }

    runner = ABTestRunner(
        run_date=run_date,
        watchlist=watchlist,
        collected=collected,
        news_map=news_map,
        analyses=analyses,
        model_profile=load_model_profile(profile_name="economy"),
        output_root=output_root,
    )
    selected_tickers = runner.select_weekly_sample(sample_size=5)
    result = runner.run_test(selected_tickers, variant_a, variant_b)
    result.update(
        {
            "run_date": run_date.isoformat(),
            "sample_size": min(5, len(selected_tickers)),
        }
    )
    return result


def _template_meta(template: PromptTemplate) -> dict[str, str]:
    return {"name": template.name, "version": template.version}


def _validation_for_ticker(result: ModuleResult, ticker: str) -> dict[str, Any]:
    diagnostics = result.diagnostics or {}
    details = diagnostics.get("validation_details", {})
    entry = details.get(ticker, {}) if isinstance(details, dict) else {}
    return entry if isinstance(entry, dict) else {}


def _variant_detail(
    payload: dict[str, Any],
    validation: dict[str, Any],
    signal_rows: list[dict[str, str]],
    ticker: str,
) -> dict[str, Any]:
    signal_text = str(payload.get("signal_or_takeaway", "")).strip()
    warning_count = int(validation.get("warning_count", 0) or 0)
    fact_accuracy_score = max(0.0, 1.0 - min(1.0, warning_count / 4.0))
    signal_quality = _estimate_signal_quality(signal_rows, ticker, _classify_signal_direction(signal_text))
    return {
        "signal_or_takeaway": signal_text,
        "signal_direction": _classify_signal_direction(signal_text),
        "fact_accuracy_score": round(fact_accuracy_score, 4),
        "validation": validation,
        "signal_quality": signal_quality,
    }


def _estimate_signal_quality(
    signal_rows: list[dict[str, str]],
    ticker: str,
    direction: str,
) -> dict[str, Any]:
    matched = [
        row for row in signal_rows
        if str(row.get("ticker", "")).strip().upper() == ticker.upper()
        and str(row.get("signal_direction", "")).strip().lower() == direction
        and str(row.get("evaluated_5d", "")).strip().lower() == "true"
    ]
    returns = [_parse_percent(row.get("return_5d", "")) for row in matched]
    usable = [value for value in returns if value is not None]
    if not usable:
        return {
            "evaluated_samples": 0,
            "avg_return_5d": "N/A",
            "win_rate_5d": "N/A",
        }
    wins = sum(1 for value in usable if (value > 0 if direction != "bear" else value < 0))
    avg_return = sum(usable) / len(usable)
    win_rate = wins / len(usable) * 100
    return {
        "evaluated_samples": len(usable),
        "avg_return_5d": f"{avg_return:+.2f}%",
        "win_rate_5d": f"{win_rate:.1f}%",
    }


def _preferred_variant(variant_a: dict[str, Any], variant_b: dict[str, Any]) -> str:
    score_a = _variant_score(variant_a)
    score_b = _variant_score(variant_b)
    if score_a > score_b:
        return "a"
    if score_b > score_a:
        return "b"
    return "tie"


def _variant_score(variant: dict[str, Any]) -> float:
    fact_accuracy = float(variant.get("fact_accuracy_score", 0.0) or 0.0)
    avg_return = _parse_percent(variant.get("signal_quality", {}).get("avg_return_5d", "N/A")) or 0.0
    return fact_accuracy + (avg_return / 100.0)


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {}
    variant_a_scores = [float(item["variant_a"]["fact_accuracy_score"]) for item in results]
    variant_b_scores = [float(item["variant_b"]["fact_accuracy_score"]) for item in results]
    preferred_counts = {"a": 0, "b": 0, "tie": 0}
    for item in results:
        preferred_counts[item["preferred_variant"]] = preferred_counts.get(item["preferred_variant"], 0) + 1
    return {
        "variant_a_avg_fact_accuracy": round(sum(variant_a_scores) / len(variant_a_scores), 4),
        "variant_b_avg_fact_accuracy": round(sum(variant_b_scores) / len(variant_b_scores), 4),
        "preferred_counts": preferred_counts,
    }


def _classify_signal_direction(signal_text: str) -> str:
    normalized = signal_text.strip().lower()
    if any(token in normalized for token in _BEARISH_TERMS):
        return "bear"
    if any(token in normalized for token in _BULLISH_TERMS):
        return "bull"
    return "neutral"


def _parse_percent(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text == "N/A":
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None
