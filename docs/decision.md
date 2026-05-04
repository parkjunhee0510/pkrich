# Decision

## Codex Routing

- Read when the task changes `src/decision/`, conviction scoring, regime logic, factor registration, or action generation.
- Pair with `docs/state.md` when the change depends on signal history or portfolio-derived state.
- Then inspect `src/decision/` and only the specific state utilities involved.

## Responsibilities

* Plugin-based factor scoring
* Regime-aware weighting and normalization
* Final `buy/watch/avoid` decision generation
* `factor_reasoning` surfaced for downstream output consumers
* `final_conviction` is the source of truth for `TickerDecision.conviction` and action thresholds; `raw_conviction` remains available for comparison
* Hidden rollback env `DECISION_CONFIDENCE_FORCE_RAW=1` restores the raw conviction/action path

## Data Quality Score

The decision layer owns the final `data_quality_score` used by confidence adjustment. The score combines analyzer validation, price freshness, news coverage, source diversity, fallback depth, missing fundamentals, and macro context availability.

The initial gate is shadow-only. `confidence_meta.data_quality_gate` records whether a low score would cap a `buy` to `watch`, but default official action behavior remains driven by the existing conviction and confidence calculation. Output and web code serialize this metadata without recomputing it.

## Action Change Reasons

Action change reasons are deterministic explanatory metadata for output analytics. They compare each current `TickerDecision` with the most recent prior tracked signal row for the same ticker, including previous action, conviction, regime, top factor, and confidence metadata.

This comparison is observational only. It must not mutate `TickerDecision`, recalculate action thresholds, alter conviction, or feed back into official decision generation. Output writers may serialize the reasons after decisions are finalized and signal rows are recorded.

## Key Components

* `DecisionFactor`
* factor registry under `src/decision/factors/`
* `MarketRegime` and sub-regime classification in `src/decision/market_regime.py`
* `ConvictionScorer`
* `generate_decisions(...)` in `src/decision/decision_layer.py`

Included factor families:
* macro regime factors
* macro event factors
* fundamentals, momentum, valuation, and other registered scoring factors

## Must Not

* Fetch external data
* Write output files directly
* Bypass datastore or state utilities for persisted history

## Boundary Notes

* Inputs come from collected data, analyzer outputs, and reproducible stored state
* Decision logic stays rule-based even when upstream analysis uses LLMs
* Changes that alter signal-history usage should also review `docs/state.md`
