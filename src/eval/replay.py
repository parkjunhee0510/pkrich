from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence


@dataclass(frozen=True)
class ReplayConfig:
    tickers: Sequence[str]
    runs_per_ticker: int
    max_cost_usd: float
    dry_run: bool = False
    estimated_cost_per_call_usd: float = 0.05


@dataclass
class ReplayResult:
    outputs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    actual_cost_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    aborted: bool = False
    abort_reason: str | None = None


class LLMReplayClient(ABC):
    @abstractmethod
    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        raise NotImplementedError


def estimate_cost(*, tickers: Sequence[str], runs_per_ticker: int,
                  cost_per_call_usd: float) -> float:
    return len(tickers) * runs_per_ticker * cost_per_call_usd


class OpenAIReplayClient(LLMReplayClient):
    """Lazy-imported adapter over the analyzer's existing llm_runtime.

    Kept lazy so unit tests don't pay the import cost or require an API key.
    Real production use replays signal_takeaway_module for the requested ticker.
    """

    def __init__(self, model_profile: str) -> None:
        self.model_profile = model_profile

    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        del run_index
        from src.analyzer.base import AnalysisContext
        from src.analyzer.modules.signal_takeaway_module import SignalTakeawayModule
        from src.analyzer.llm_runtime import run_structured_llm_module  # lazy
        from src.analyzer.payloads import build_fallback_payloads, build_raw_payloads
        from src.types import CollectedTickerData, WatchlistItem
        from src.utils.model_config import load_model_profile

        watchlist = [WatchlistItem(ticker=ticker, name=ticker)]
        collected = {
            ticker: CollectedTickerData(
                ticker=ticker,
                name=ticker,
                sector="",
                price=None,
                change_percent=None,
                currency="USD",
                market_cap="N/A",
                pe_ratio="N/A",
                summary_note="N/A",
            )
        }
        news_map: dict[str, list[Any]] = {ticker: []}
        raw_payloads = build_raw_payloads(watchlist, collected, news_map)
        fallback_payloads = build_fallback_payloads(
            watchlist,
            collected,
            news_map,
            date.today(),
            raw_payload_by_ticker=raw_payloads,
        )
        ctx = AnalysisContext(
            watchlist=watchlist,
            collected=collected,
            news_map=news_map,
            run_date=date.today(),
            model_profile=load_model_profile(profile_name=self.model_profile),
            raw_payload_by_ticker=raw_payloads,
            fallback_payload_by_ticker=fallback_payloads,
            intermediate_results={
                ticker: dict(fallback_payloads.get(ticker, {}))
            },
        )
        module_result = run_structured_llm_module(SignalTakeawayModule(), ctx)
        result = module_result.results_by_ticker.get(ticker, {})
        summary = str(result.get("signal_or_takeaway") or result.get("summary") or "")
        return {
            "action": result.get("action") or _classify_action(summary),
            "summary": summary,
            "cost_usd": float(result.get("cost_usd") or 0.0),
        }


def run_replay(*, client: LLMReplayClient, config: ReplayConfig) -> ReplayResult:
    estimated = estimate_cost(
        tickers=config.tickers,
        runs_per_ticker=config.runs_per_ticker,
        cost_per_call_usd=config.estimated_cost_per_call_usd,
    )
    result = ReplayResult(estimated_cost_usd=estimated)
    if config.dry_run:
        return result

    for ticker in config.tickers:
        result.outputs.setdefault(ticker, [])
        for i in range(config.runs_per_ticker):
            if result.actual_cost_usd >= config.max_cost_usd:
                result.aborted = True
                result.abort_reason = f"cost cap {config.max_cost_usd} reached"
                return result
            response = client.call(ticker, i)
            cost = float(response.get("cost_usd") or 0.0)
            if result.actual_cost_usd + cost > config.max_cost_usd:
                result.aborted = True
                result.abort_reason = (
                    f"next call ({cost}) would exceed cap {config.max_cost_usd}"
                )
                return result
            result.actual_cost_usd += cost
            result.outputs[ticker].append(response)
    return result


def _classify_action(text: str) -> str:
    normalized = text.strip().lower()
    if any(token in normalized for token in ("avoid", "sell", "bear")):
        return "avoid"
    if any(token in normalized for token in ("buy", "bull")):
        return "buy"
    return "watch"
