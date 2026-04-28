from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    Real production use replays research_note for the requested ticker.
    """

    def __init__(self, model_profile: str) -> None:
        self.model_profile = model_profile

    def call(self, ticker: str, run_index: int) -> dict[str, Any]:
        from src.analyzer.llm_runtime import run_structured_llm_module  # lazy
        result = run_structured_llm_module(  # type: ignore[call-arg]
            module_name="research_note",
            ticker=ticker,
            model_profile=self.model_profile,
        )
        return {
            "action": result.get("action"),
            "summary": result.get("summary"),
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
