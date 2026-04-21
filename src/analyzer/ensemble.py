from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from src.analyzer.orchestrator import AnalysisOrchestrator
from src.analyzer.payloads import payloads_from_analyses
from src.decision.decision_layer import generate_decisions
from src.types import (
    CollectedTickerData,
    MarketRegime,
    NewsItem,
    PortfolioSummary,
    TickerAnalysis,
    TickerDecision,
    WatchlistItem,
)
from src.utils.model_config import EnsembleConfig


@dataclass(frozen=True)
class EnsembleResult:
    analyses: list[TickerAnalysis]
    economy_analyses_by_ticker: dict[str, TickerAnalysis]
    deep_analyses_by_ticker: dict[str, TickerAnalysis]
    consensus_by_ticker: dict[str, dict[str, Any]]
    portfolio_result: dict[str, Any]
    diagnostics: dict[str, Any]
    final_decisions: list[TickerDecision]


class AnalysisEnsemble:
    def __init__(
        self,
        economy_orchestrator: AnalysisOrchestrator,
        deep_orchestrator: AnalysisOrchestrator,
        tie_break_orchestrator: AnalysisOrchestrator | None,
        config: EnsembleConfig,
    ) -> None:
        self.economy_orchestrator = economy_orchestrator
        self.deep_orchestrator = deep_orchestrator
        self.tie_break_orchestrator = tie_break_orchestrator
        self.config = config

    def analyze_with_consensus(
        self,
        watchlist: list[WatchlistItem],
        collected: dict[str, CollectedTickerData],
        news_map: dict[str, list[NewsItem]],
        run_date: date,
        *,
        market_regime: MarketRegime,
        signal_stats: dict[str, Any] | None = None,
        macro_context: dict[str, Any] | None = None,
        signal_history_map: dict[str, list[dict[str, str]]] | None = None,
        portfolio_account_size: float | None = None,
        portfolio_summary: PortfolioSummary | None = None,
        portfolio_risk: dict[str, Any] | None = None,
        peer_candidates_by_ticker: dict[str, list[dict[str, Any]]] | None = None,
    ) -> EnsembleResult:
        signal_stats = signal_stats or {}
        portfolio_risk = portfolio_risk or {}

        economy_analyses = self.economy_orchestrator.analyze_all(
            watchlist,
            collected,
            news_map,
            run_date,
            macro_context=macro_context,
            signal_history_map=signal_history_map,
            portfolio_account_size=portfolio_account_size,
            portfolio_summary=portfolio_summary,
            peer_candidates_by_ticker=peer_candidates_by_ticker,
        )
        economy_map = {analysis.ticker: analysis for analysis in economy_analyses}
        effective_portfolio_risk = portfolio_risk or self.economy_orchestrator.portfolio_result.get("portfolio_risk", {})
        economy_decisions = generate_decisions(
            economy_analyses,
            collected,
            market_regime,
            signal_stats,
            run_date,
            portfolio_risk=effective_portfolio_risk,
            macro_context=macro_context,
        )
        economy_decision_map = {decision.ticker: decision for decision in economy_decisions}
        eligible_tickers = [
            item.ticker
            for item in watchlist
            if _is_ensemble_target(economy_decision_map.get(item.ticker), self.config)
        ]
        target_tickers = _select_target_tickers(eligible_tickers, economy_decision_map, watchlist, self.config)
        skipped_due_to_cap = [ticker for ticker in eligible_tickers if ticker not in target_tickers]

        deep_map: dict[str, TickerAnalysis] = {}
        deep_decision_map: dict[str, TickerDecision] = {}
        tie_break_map: dict[str, TickerAnalysis] = {}
        tie_break_decision_map: dict[str, TickerDecision] = {}
        diagnostics: dict[str, Any] = {
            "ensemble_enabled": self.config.enabled,
            "eligible_tickers": eligible_tickers,
            "selected_tickers": target_tickers,
            "skipped_due_to_cap": skipped_due_to_cap,
            "trigger_range": list(self.config.trigger_range),
            "max_daily_ensemble": self.config.max_daily_ensemble,
            "second_model": self.config.second_model,
            "second_prompt": self.config.second_prompt,
            "third_model": self.config.third_model,
            "third_prompt": self.config.third_prompt,
            "ensemble_target_tickers": target_tickers,
            "economy_executed_modules": self.economy_orchestrator.diagnostics.get("executed_modules", []),
            "deep_executed_modules": [],
            "tie_break_executed_modules": [],
            "third_review_tickers": [],
        }
        portfolio_result = dict(self.economy_orchestrator.portfolio_result)

        if target_tickers:
            target_watchlist = [item for item in watchlist if item.ticker in target_tickers]
            target_collected = {ticker: collected[ticker] for ticker in target_tickers if ticker in collected}
            target_news = {ticker: news_map.get(ticker, []) for ticker in target_tickers}
            target_signal_history = {
                ticker: (signal_history_map or {}).get(ticker, [])
                for ticker in target_tickers
            }
            target_peer_candidates = {
                ticker: (peer_candidates_by_ticker or {}).get(ticker, [])
                for ticker in target_tickers
            }
            initial_payloads = {
                ticker: payload
                for ticker, payload in payloads_from_analyses(economy_analyses).items()
                if ticker in target_tickers
            }
            deep_analyses = self.deep_orchestrator.analyze_all(
                target_watchlist,
                target_collected,
                target_news,
                run_date,
                macro_context=macro_context,
                signal_history_map=target_signal_history,
                portfolio_account_size=portfolio_account_size,
                portfolio_summary=portfolio_summary,
                peer_candidates_by_ticker=target_peer_candidates,
                execution_mode="llm_only",
                initial_intermediate_results=initial_payloads,
            )
            deep_map = {analysis.ticker: analysis for analysis in deep_analyses}
            diagnostics["deep_executed_modules"] = self.deep_orchestrator.diagnostics.get("executed_modules", [])
            if not portfolio_result:
                portfolio_result.update(self.deep_orchestrator.portfolio_result)
            deep_decisions = generate_decisions(
                deep_analyses,
                target_collected,
                market_regime,
                signal_stats,
                run_date,
                portfolio_risk=effective_portfolio_risk,
                macro_context=macro_context,
            )
            deep_decision_map = {decision.ticker: decision for decision in deep_decisions}

            conflicted_tickers = [
                ticker
                for ticker in target_tickers
                if _is_conflicted_pair(economy_decision_map.get(ticker), deep_decision_map.get(ticker))
            ]
            diagnostics["third_review_tickers"] = conflicted_tickers

            if conflicted_tickers and self.tie_break_orchestrator is not None:
                tie_break_watchlist = [item for item in watchlist if item.ticker in conflicted_tickers]
                tie_break_collected = {ticker: collected[ticker] for ticker in conflicted_tickers if ticker in collected}
                tie_break_news = {ticker: news_map.get(ticker, []) for ticker in conflicted_tickers}
                tie_break_signal_history = {
                    ticker: (signal_history_map or {}).get(ticker, [])
                    for ticker in conflicted_tickers
                }
                tie_break_peer_candidates = {
                    ticker: (peer_candidates_by_ticker or {}).get(ticker, [])
                    for ticker in conflicted_tickers
                }
                tie_break_initial_payloads = {
                    ticker: payload
                    for ticker, payload in initial_payloads.items()
                    if ticker in conflicted_tickers
                }
                tie_break_analyses = self.tie_break_orchestrator.analyze_all(
                    tie_break_watchlist,
                    tie_break_collected,
                    tie_break_news,
                    run_date,
                    macro_context=macro_context,
                    signal_history_map=tie_break_signal_history,
                    portfolio_account_size=portfolio_account_size,
                    portfolio_summary=portfolio_summary,
                    peer_candidates_by_ticker=tie_break_peer_candidates,
                    execution_mode="llm_only",
                    initial_intermediate_results=tie_break_initial_payloads,
                )
                tie_break_map = {analysis.ticker: analysis for analysis in tie_break_analyses}
                diagnostics["tie_break_executed_modules"] = self.tie_break_orchestrator.diagnostics.get("executed_modules", [])
                tie_break_decisions = generate_decisions(
                    tie_break_analyses,
                    tie_break_collected,
                    market_regime,
                    signal_stats,
                    run_date,
                    portfolio_risk=effective_portfolio_risk,
                    macro_context=macro_context,
                )
                tie_break_decision_map = {decision.ticker: decision for decision in tie_break_decisions}

        consensus_by_ticker: dict[str, dict[str, Any]] = {}
        final_analyses: list[TickerAnalysis] = []
        for item in watchlist:
            ticker = item.ticker
            economy_analysis = economy_map.get(ticker)
            deep_analysis = deep_map.get(ticker)
            tie_break_analysis = tie_break_map.get(ticker)
            economy_decision = economy_decision_map.get(ticker)
            deep_decision = deep_decision_map.get(ticker)
            tie_break_decision = tie_break_decision_map.get(ticker)
            selected = ticker in target_tickers
            consensus = _build_consensus_payload(
                economy_decision,
                deep_decision,
                tie_break_decision=tie_break_decision,
                selected=selected,
                enabled=self.config.enabled,
                skipped_due_to_cap=ticker in skipped_due_to_cap,
            )
            consensus_by_ticker[ticker] = consensus
            source_analysis = tie_break_analysis or deep_analysis or economy_analysis
            if source_analysis is None:
                continue
            final_analyses.append(replace(source_analysis, analysis_consensus=consensus))

        final_decisions = generate_decisions(
            final_analyses,
            collected,
            market_regime,
            signal_stats,
            run_date,
            portfolio_risk=effective_portfolio_risk,
            macro_context=macro_context,
        )
        final_decisions = apply_consensus_to_decisions(final_decisions, consensus_by_ticker)

        return EnsembleResult(
            analyses=final_analyses,
            economy_analyses_by_ticker=economy_map,
            deep_analyses_by_ticker=deep_map,
            consensus_by_ticker=consensus_by_ticker,
            portfolio_result=portfolio_result,
            diagnostics=diagnostics,
            final_decisions=final_decisions,
        )


def apply_consensus_to_decisions(
    decisions: list[TickerDecision],
    consensus_by_ticker: dict[str, dict[str, Any]],
) -> list[TickerDecision]:
    updated: list[TickerDecision] = []
    for decision in decisions:
        consensus = consensus_by_ticker.get(decision.ticker, {})
        final_consensus = str(consensus.get("final_consensus", "single"))
        if consensus.get("status") != "conflicted":
            updated.append(replace(decision, final_consensus=final_consensus))
            continue
        economy_action = consensus.get("economy_action", "watch")
        economy_reason = str(consensus.get("economy_reason", "")).strip()
        conflict_note = f"Consensus conflict: economy={economy_action}"
        if economy_reason:
            conflict_note = f"{conflict_note} ({economy_reason})"
        reason = f"{decision.reason} / {conflict_note}" if decision.reason else conflict_note
        updated.append(replace(decision, reason=reason, final_consensus=final_consensus))
    return updated


def _is_ensemble_target(decision: TickerDecision | None, config: EnsembleConfig) -> bool:
    if decision is None or not config.enabled:
        return False
    low, high = config.trigger_range
    return low <= decision.conviction <= high


def _select_target_tickers(
    eligible_tickers: list[str],
    decision_map: dict[str, TickerDecision],
    watchlist: list[WatchlistItem],
    config: EnsembleConfig,
) -> list[str]:
    if not config.enabled or config.max_daily_ensemble <= 0:
        return []
    watchlist_order = {item.ticker: index for index, item in enumerate(watchlist)}

    def _sort_key(ticker: str) -> tuple[float, float, int]:
        conviction = decision_map[ticker].conviction
        edge_distance = min(abs(conviction - 35), abs(conviction - 65))
        ambiguity = abs(conviction - 50)
        return (edge_distance, ambiguity, watchlist_order.get(ticker, 9999))

    ranked = sorted(eligible_tickers, key=_sort_key)
    return ranked[: config.max_daily_ensemble]


def _direction_bucket(action: str | None) -> str:
    if action == "buy":
        return "bullish"
    if action == "avoid":
        return "bearish"
    return "neutral"


def _is_conflicted_pair(
    economy_decision: TickerDecision | None,
    deep_decision: TickerDecision | None,
) -> bool:
    if economy_decision is None or deep_decision is None:
        return False
    return _direction_bucket(economy_decision.action) != _direction_bucket(deep_decision.action)


def _build_consensus_payload(
    economy_decision: TickerDecision | None,
    deep_decision: TickerDecision | None,
    *,
    tie_break_decision: TickerDecision | None = None,
    selected: bool,
    enabled: bool,
    skipped_due_to_cap: bool,
) -> dict[str, Any]:
    if deep_decision is None:
        return {
            "status": "not_applicable",
            "direction_agreement": None,
            "selection_reason": _selection_reason(enabled, selected, skipped_due_to_cap),
            "third_review_completed": False,
            "final_consensus": "single",
        }
    economy_action = economy_decision.action if economy_decision else "watch"
    deep_action = deep_decision.action
    direction_agreement = _direction_bucket(economy_action) == _direction_bucket(deep_action)
    final_consensus = "agree" if direction_agreement else "conflict"
    status = "agreed" if direction_agreement else "conflicted"
    if tie_break_decision is not None and not direction_agreement:
        final_consensus = "resolved"
        status = "resolved"
    return {
        "status": status,
        "economy_action": economy_action,
        "economy_conviction": economy_decision.conviction if economy_decision else None,
        "economy_reason": economy_decision.reason if economy_decision else "",
        "deep_action": deep_action,
        "deep_conviction": deep_decision.conviction,
        "deep_reason": deep_decision.reason,
        "tie_break_action": tie_break_decision.action if tie_break_decision else None,
        "tie_break_conviction": tie_break_decision.conviction if tie_break_decision else None,
        "tie_break_reason": tie_break_decision.reason if tie_break_decision else "",
        "direction_agreement": direction_agreement,
        "conflicted": not direction_agreement,
        "confidence_delta": 5 if direction_agreement else 0,
        "selection_reason": "selected",
        "third_review_completed": tie_break_decision is not None,
        "final_consensus": final_consensus,
        "final_action": tie_break_decision.action if tie_break_decision else deep_action,
    }


def _selection_reason(enabled: bool, selected: bool, skipped_due_to_cap: bool) -> str:
    if not enabled:
        return "disabled"
    if selected:
        return "selected"
    if skipped_due_to_cap:
        return "cap_exceeded"
    return "out_of_range"
