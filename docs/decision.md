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

By default, the data-quality gate remains shadow-only. `confidence_meta.data_quality_gate` records whether a low score would cap a `buy` to `watch`, while official action behavior remains driven by the existing conviction and confidence calculation.

Set `DECISION_DATA_QUALITY_GATE_MODE=enforce` to promote the gate from shadow mode. In enforced mode, a `buy` with `data_quality_score < 0.6` is capped to `watch`, and the reason text records that the data-quality gate was applied. Output and web code serialize this metadata without recomputing it.

## Search Evidence Quality

Search evidence quality is attached to `TickerDecision.confidence_meta` after official rule-based actions are generated. By default this remains observational: `search_evidence_score` and `search_quality_gate` show whether a weak-evidence `buy` would be capped to `watch`, while the official `TickerDecision.action` remains unchanged.

Set `DECISION_SEARCH_QUALITY_GATE_MODE=enforce` to promote the search gate from shadow mode. In enforced mode, a `buy` with `search_evidence_score < 0.55` is capped to `watch`, `confidence_meta.search_quality_gate.enforced` is set to `true`, and the reason text records that the search-evidence gate was applied. Missing search payloads are marked as unavailable and do not penalize a ticker.

`src.decision.search_quality.attach_search_quality_shadow(...)` consumes the normalized `search_evidence.json` contract from the collector/output side. It does not fetch data, call an LLM, or write artifacts.

## Key Components

* `DecisionFactor`
* factor registry under `src/decision/factors/`
* `MarketRegime` and sub-regime classification in `src/decision/market_regime.py`
* `ConvictionScorer`
* `generate_decisions(...)` in `src/decision/decision_layer.py`
* `attach_search_quality_shadow(...)` in `src/decision/search_quality.py`

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
