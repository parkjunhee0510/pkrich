from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.types import CollectedTickerData, NewsItem, PortfolioSummary, WatchlistItem
from src.utils.model_config import ModelProfile


@dataclass(frozen=True)
class AnalysisContext:
    watchlist: list[WatchlistItem]
    collected: dict[str, CollectedTickerData]
    news_map: dict[str, list[NewsItem]]
    run_date: date
    portfolio_summary: PortfolioSummary | None = None
    macro_context: dict[str, Any] | None = None
    signal_history_map: dict[str, list[dict[str, str]]] | None = None
    portfolio_account_size: float | None = None
    model_profile: ModelProfile | None = None
    logger: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    available_inputs: set[str] = field(default_factory=set)
    raw_payload_by_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    fallback_payload_by_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    intermediate_results: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleResult:
    results_by_ticker: dict[str, dict[str, Any]] = field(default_factory=dict)
    portfolio_result: dict[str, Any] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


class AnalysisModule(ABC):
    name: str = "analysis_module"
    requires: set[str] = set()
    produces: set[str] = set()
    priority: int = 100
    llm_required: bool = False

    @abstractmethod
    def analyze(self, ctx: AnalysisContext) -> ModuleResult:
        raise NotImplementedError

    def estimate_tokens(self, ctx: AnalysisContext) -> int:
        return 0


class StructuredLLMModule(AnalysisModule, ABC):
    llm_required: bool = True

    @abstractmethod
    def build_batch_payload(
        self,
        ctx: AnalysisContext,
        batch_tickers: list[str],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def build_system_prompt(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_user_prompt(
        self,
        batch_payload: list[dict[str, Any]],
        ctx: AnalysisContext,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def response_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def response_schema_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_batch_response(
        self,
        content: str,
        batch_tickers: list[str],
        ctx: AnalysisContext,
    ) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fallback_for_ticker(
        self,
        ticker: str,
        ctx: AnalysisContext,
    ) -> dict[str, Any]:
        raise NotImplementedError


def sort_modules(modules: list[AnalysisModule]) -> list[AnalysisModule]:
    return sorted(modules, key=lambda module: (module.priority, module.name))
