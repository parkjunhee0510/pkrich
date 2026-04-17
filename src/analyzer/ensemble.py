from __future__ import annotations

import statistics
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

# Conviction calibration modifiers (see src/decision/calibration.py for validation).
# AGREE_BOOST: max boost when 3 models agree with zero spread.
# SPREAD_K: shrinks the boost proportionally to stdev of model convictions.
# CONFLICT_SHRINK: compresses mean conviction toward 50 on full disagreement.
AGREE_BOOST = 8.0
SPREAD_K = 0.5
CONFLICT_SHRINK = 0.6

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
    third_analyses_by_ticker: dict[str, TickerAnalysis]
    consensus_by_ticker: dict[str, dict[str, Any]]
    portfolio_result: dict[str, Any]
    diagnostics: dict[str, Any]
    final_decisions: list[TickerDecision]


class AnalysisEnsemble:
    def __init__(
        self,
        economy_orchestrator: AnalysisOrchestrator,
        deep_orchestrator: AnalysisOrchestrator,
        tie_break_orchestrator: AnalysisOrchestrator,
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
        )
        economy_decision_map = {decision.ticker: decision for decision in economy_decisions}

        portfolio_tickers: set[str] = set()
        if portfolio_summary is not None:
            portfolio_tickers = {
                position.ticker for position in portfolio_summary.positions
            }

        eligible_tickers = [
            item.ticker
            for item in watchlist
            if _is_ensemble_target(
                economy_decision_map.get(item.ticker),
                self.config,
                in_portfolio=item.ticker in portfolio_tickers,
            )
        ]
        target_tickers = _select_target_tickers(
            eligible_tickers,
            economy_decision_map,
            watchlist,
            self.config,
            portfolio_tickers=portfolio_tickers,
        )
        skipped_due_to_cap = [ticker for ticker in eligible_tickers if ticker not in target_tickers]

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
            "third_executed_modules": [],
            "conflicted_tickers": [],
            "third_review_tickers": [],
            "portfolio_tickers": sorted(portfolio_tickers),
            "routing_log": build_routing_log(
                watchlist,
                economy_decision_map,
                target_tickers,
                self.config,
                portfolio_tickers=portfolio_tickers,
                run_date=run_date,
            ),
        }
        portfolio_result = dict(self.economy_orchestrator.portfolio_result)

        deep_map: dict[str, TickerAnalysis] = {}
        deep_decision_map: dict[str, TickerDecision] = {}
        economy_payloads = payloads_from_analyses(economy_analyses)
        if target_tickers:
            deep_analyses = self.deep_orchestrator.analyze_all(
                [item for item in watchlist if item.ticker in target_tickers],
                {ticker: collected[ticker] for ticker in target_tickers if ticker in collected},
                {ticker: news_map.get(ticker, []) for ticker in target_tickers},
                run_date,
                macro_context=macro_context,
                signal_history_map={
                    ticker: (signal_history_map or {}).get(ticker, [])
                    for ticker in target_tickers
                },
                portfolio_account_size=portfolio_account_size,
                portfolio_summary=portfolio_summary,
                peer_candidates_by_ticker={
                    ticker: (peer_candidates_by_ticker or {}).get(ticker, [])
                    for ticker in target_tickers
                },
                execution_mode="llm_only",
                initial_intermediate_results={
                    ticker: economy_payloads[ticker]
                    for ticker in target_tickers
                    if ticker in economy_payloads
                },
            )
            deep_map = {analysis.ticker: analysis for analysis in deep_analyses}
            diagnostics["deep_executed_modules"] = self.deep_orchestrator.diagnostics.get("executed_modules", [])
            if not portfolio_result:
                portfolio_result.update(self.deep_orchestrator.portfolio_result)
            deep_decisions = generate_decisions(
                deep_analyses,
                {ticker: collected[ticker] for ticker in target_tickers if ticker in collected},
                market_regime,
                signal_stats,
                run_date,
                portfolio_risk=effective_portfolio_risk,
            )
            deep_decision_map = {decision.ticker: decision for decision in deep_decisions}

        conflicted_tickers = [
            ticker
            for ticker in target_tickers
            if _is_direction_conflict(
                economy_decision_map.get(ticker),
                deep_decision_map.get(ticker),
            )
        ]
        diagnostics["conflicted_tickers"] = conflicted_tickers

        third_map: dict[str, TickerAnalysis] = {}
        third_decision_map: dict[str, TickerDecision] = {}
        if conflicted_tickers:
            third_analyses = self.tie_break_orchestrator.analyze_all(
                [item for item in watchlist if item.ticker in conflicted_tickers],
                {ticker: collected[ticker] for ticker in conflicted_tickers if ticker in collected},
                {ticker: news_map.get(ticker, []) for ticker in conflicted_tickers},
                run_date,
                macro_context=macro_context,
                signal_history_map={
                    ticker: (signal_history_map or {}).get(ticker, [])
                    for ticker in conflicted_tickers
                },
                portfolio_account_size=portfolio_account_size,
                portfolio_summary=portfolio_summary,
                peer_candidates_by_ticker={
                    ticker: (peer_candidates_by_ticker or {}).get(ticker, [])
                    for ticker in conflicted_tickers
                },
                execution_mode="llm_only",
                initial_intermediate_results={
                    ticker: economy_payloads[ticker]
                    for ticker in conflicted_tickers
                    if ticker in economy_payloads
                },
            )
            third_map = {analysis.ticker: analysis for analysis in third_analyses}
            diagnostics["third_executed_modules"] = self.tie_break_orchestrator.diagnostics.get("executed_modules", [])
            diagnostics["third_review_tickers"] = conflicted_tickers
            third_decisions = generate_decisions(
                third_analyses,
                {ticker: collected[ticker] for ticker in conflicted_tickers if ticker in collected},
                market_regime,
                signal_stats,
                run_date,
                portfolio_risk=effective_portfolio_risk,
            )
            third_decision_map = {decision.ticker: decision for decision in third_decisions}

        consensus_by_ticker: dict[str, dict[str, Any]] = {}
        final_analyses: list[TickerAnalysis] = []
        for item in watchlist:
            ticker = item.ticker
            economy_analysis = economy_map.get(ticker)
            deep_analysis = deep_map.get(ticker)
            third_analysis = third_map.get(ticker)
            consensus = _build_consensus_payload(
                economy_decision_map.get(ticker),
                deep_decision_map.get(ticker),
                third_decision_map.get(ticker),
                selected=ticker in target_tickers,
                enabled=self.config.enabled,
                skipped_due_to_cap=ticker in skipped_due_to_cap,
            )
            consensus_by_ticker[ticker] = consensus

            source_analysis = third_analysis or deep_analysis or economy_analysis
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
        )
        final_decisions = apply_consensus_to_decisions(final_decisions, consensus_by_ticker)

        return EnsembleResult(
            analyses=final_analyses,
            economy_analyses_by_ticker=economy_map,
            deep_analyses_by_ticker=deep_map,
            third_analyses_by_ticker=third_map,
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
        reason = decision.reason

        adjustment = _compute_conviction_adjustment(consensus)
        if adjustment is not None:
            # Persist diagnostics onto the payload so Admin/json_export can show it.
            consensus["conviction_mean"] = adjustment["mean"]
            consensus["conviction_stdev"] = adjustment["stdev"]
            consensus["conviction_adjusted"] = adjustment["adjusted"]
            consensus["conviction_prior"] = decision.conviction
            consensus["conviction_sample_size"] = adjustment["sample_size"]

        if final_consensus == "resolved":
            final_action = str(consensus.get("final_action", decision.action))
            third_reason = str(consensus.get("third_reason", "")).strip()
            resolve_note = f"3차 검토로 최종 합의: {final_action}"
            if third_reason:
                resolve_note = f"{resolve_note} ({third_reason})"
            reason = f"{reason} / {resolve_note}" if reason else resolve_note
        elif final_consensus == "conflict" and consensus.get("third_action"):
            economy_action = str(consensus.get("economy_action", "watch"))
            deep_action = str(consensus.get("deep_action", "watch"))
            third_action = str(consensus.get("third_action", decision.action))
            conflict_note = f"3차 검토 후에도 불일치: 1차 {economy_action}, 2차 {deep_action}, 3차 {third_action}"
            reason = f"{reason} / {conflict_note}" if reason else conflict_note
        elif consensus.get("status") == "conflicted":
            economy_action = str(consensus.get("economy_action", "watch"))
            economy_reason = str(consensus.get("economy_reason", "")).strip()
            conflict_note = f"합의 불일치: 1차 판단은 {economy_action}"
            if economy_reason:
                conflict_note = f"{conflict_note} ({economy_reason})"
            reason = f"{reason} / {conflict_note}" if reason else conflict_note

        new_conviction = decision.conviction
        if adjustment is not None:
            new_conviction = adjustment["adjusted"]
            delta = new_conviction - decision.conviction
            if delta != 0:
                direction = "↑" if delta > 0 else "↓"
                calibration_note = (
                    f"앙상블 보정: {decision.conviction}→{new_conviction} "
                    f"({direction}{abs(delta)}, spread σ={adjustment['stdev']})"
                )
                reason = f"{reason} / {calibration_note}" if reason else calibration_note

        updated.append(
            replace(
                decision,
                reason=reason,
                final_consensus=final_consensus,
                conviction=new_conviction,
            )
        )
    return updated


def _is_ensemble_target(
    decision: TickerDecision | None,
    config: EnsembleConfig,
    *,
    in_portfolio: bool = False,
) -> bool:
    if decision is None or not config.enabled:
        return False
    if config.portfolio_priority and in_portfolio:
        return True
    low, high = config.trigger_range
    return low <= decision.conviction <= high


def _classify_routing_reason(
    decision: TickerDecision | None,
    config: EnsembleConfig,
    *,
    in_portfolio: bool,
) -> str:
    if decision is None:
        return "no_decision"
    if not config.enabled:
        return "ensemble_disabled"
    if config.portfolio_priority and in_portfolio:
        return "portfolio_priority"
    low, high = config.trigger_range
    if decision.conviction < low:
        return "below_range"
    if decision.conviction > high:
        return "above_range"
    return "in_trigger_range"


def _select_target_tickers(
    eligible_tickers: list[str],
    decision_map: dict[str, TickerDecision],
    watchlist: list[WatchlistItem],
    config: EnsembleConfig,
    *,
    portfolio_tickers: set[str] | None = None,
) -> list[str]:
    if not config.enabled:
        return []
    portfolio_tickers = portfolio_tickers or set()
    watchlist_order = {item.ticker: index for index, item in enumerate(watchlist)}

    def _sort_key(ticker: str) -> tuple[int, float, float, int]:
        conviction = decision_map[ticker].conviction
        edge_distance = min(abs(conviction - 35), abs(conviction - 65))
        ambiguity = abs(conviction - 50)
        portfolio_rank = 0 if (config.portfolio_priority and ticker in portfolio_tickers) else 1
        return (portfolio_rank, edge_distance, ambiguity, watchlist_order.get(ticker, 9999))

    ranked = sorted(eligible_tickers, key=_sort_key)
    if config.max_daily_ensemble == 0:
        return ranked
    return ranked[: config.max_daily_ensemble]


def build_routing_log(
    watchlist: list[WatchlistItem],
    decision_map: dict[str, TickerDecision],
    target_tickers: list[str],
    config: EnsembleConfig,
    *,
    portfolio_tickers: set[str] | None = None,
    run_date: date | None = None,
) -> dict[str, Any]:
    portfolio_tickers = portfolio_tickers or set()
    selected_set = set(target_tickers)
    entries: list[dict[str, Any]] = []
    for item in watchlist:
        ticker = item.ticker
        decision = decision_map.get(ticker)
        in_portfolio = ticker in portfolio_tickers
        entries.append(
            {
                "ticker": ticker,
                "conviction": decision.conviction if decision else None,
                "action": decision.action if decision else None,
                "in_portfolio": in_portfolio,
                "selected_for_deep": ticker in selected_set,
                "reason": _classify_routing_reason(decision, config, in_portfolio=in_portfolio),
            }
        )
    return {
        "schema_version": 1,
        "run_date": run_date.isoformat() if run_date else None,
        "trigger_range": list(config.trigger_range),
        "max_daily_ensemble": config.max_daily_ensemble,
        "portfolio_priority": config.portfolio_priority,
        "deep_pass_count": len(selected_set),
        "tickers": entries,
    }


def _direction_bucket(action: str | None) -> str:
    if action == "buy":
        return "bullish"
    if action == "avoid":
        return "bearish"
    return "neutral"


def _is_direction_conflict(
    economy_decision: TickerDecision | None,
    deep_decision: TickerDecision | None,
) -> bool:
    if economy_decision is None or deep_decision is None:
        return False
    return _direction_bucket(economy_decision.action) != _direction_bucket(deep_decision.action)


def _build_consensus_payload(
    economy_decision: TickerDecision | None,
    deep_decision: TickerDecision | None,
    third_decision: TickerDecision | None,
    *,
    selected: bool,
    enabled: bool,
    skipped_due_to_cap: bool,
) -> dict[str, Any]:
    if deep_decision is None:
        selection_reason = _selection_reason(enabled, selected, skipped_due_to_cap)
        return {
            "status": "not_applicable",
            "direction_agreement": None,
            "selection_reason": selection_reason,
            "final_consensus": "single",
            "third_review_completed": False,
        }

    economy_action = economy_decision.action if economy_decision else "watch"
    deep_action = deep_decision.action
    economy_direction = _direction_bucket(economy_action)
    deep_direction = _direction_bucket(deep_action)
    direction_agreement = economy_direction == deep_direction

    payload: dict[str, Any] = {
        "status": "agreed" if direction_agreement else "conflicted",
        "economy_action": economy_action,
        "economy_conviction": economy_decision.conviction if economy_decision else None,
        "economy_reason": economy_decision.reason if economy_decision else "",
        "deep_action": deep_action,
        "deep_conviction": deep_decision.conviction,
        "deep_reason": deep_decision.reason,
        "direction_agreement": direction_agreement,
        "conflicted": not direction_agreement,
        "confidence_delta": 5 if direction_agreement else 0,
        "selection_reason": "selected",
        "third_review_completed": third_decision is not None,
        "final_consensus": "agree" if direction_agreement else "conflict",
        "final_action": deep_action,
    }
    if direction_agreement:
        return payload

    if third_decision is None:
        return payload

    third_action = third_decision.action
    third_direction = _direction_bucket(third_action)
    payload.update(
        {
            "third_action": third_action,
            "third_conviction": third_decision.conviction,
            "third_reason": third_decision.reason,
        }
    )

    if third_direction == economy_direction or third_direction == deep_direction:
        payload["final_consensus"] = "resolved"
        payload["final_action"] = third_action
    else:
        payload["final_consensus"] = "conflict"
        payload["final_action"] = third_action
    return payload


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _compute_conviction_adjustment(consensus: dict[str, Any]) -> dict[str, Any] | None:
    """Derive a conviction override from model agreement.

    Inputs: per-model convictions (economy/deep/third) already stored in the
    consensus payload by `_build_pair_consensus`.

    Formula by `final_consensus`:
      - "agree" (directional agreement among available models):
            adjusted = mean + max(0, AGREE_BOOST - SPREAD_K * stdev)
        Tight spread rewarded; wide spread diluted.
      - "resolved" (tie-breaker aligned with one camp):
            adjusted = median(convictions)   # cap at median, no boost
      - "conflict" (full three-way split):
            adjusted = 50 + (mean - 50) * CONFLICT_SHRINK   # pull toward 50
      - "single" / missing data: no adjustment.

    Returns a dict with diagnostic fields (mean, stdev, adjusted) or None when
    insufficient data to adjust.
    """
    final_consensus = str(consensus.get("final_consensus", "single"))
    raw = [
        consensus.get("economy_conviction"),
        consensus.get("deep_conviction"),
        consensus.get("third_conviction"),
    ]
    convictions = [float(v) for v in raw if isinstance(v, (int, float))]
    if len(convictions) < 2 or final_consensus == "single":
        return None

    mean_c = statistics.mean(convictions)
    stdev_c = statistics.pstdev(convictions) if len(convictions) >= 2 else 0.0

    if final_consensus == "agree":
        boost = max(0.0, AGREE_BOOST - SPREAD_K * stdev_c)
        adjusted = _clamp(mean_c + boost, 0.0, 100.0)
    elif final_consensus == "resolved":
        adjusted = _clamp(statistics.median(convictions), 0.0, 100.0)
    elif final_consensus == "conflict":
        adjusted = _clamp(50.0 + (mean_c - 50.0) * CONFLICT_SHRINK, 0.0, 100.0)
    else:
        return None

    return {
        "mean": round(mean_c, 2),
        "stdev": round(stdev_c, 2),
        "adjusted": int(round(adjusted)),
        "sample_size": len(convictions),
    }


def _selection_reason(enabled: bool, selected: bool, skipped_due_to_cap: bool) -> str:
    if not enabled:
        return "disabled"
    if selected:
        return "selected"
    if skipped_due_to_cap:
        return "cap_exceeded"
    return "out_of_range"
