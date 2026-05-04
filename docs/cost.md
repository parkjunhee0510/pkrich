# Cost Management

## Codex Routing

- Read when the task can change LLM usage, model selection, batching, or paid-provider usage.
- Usually pair with `docs/analyzer.md`.
- Then inspect `config/models.yaml` and the relevant analyzer modules.

## Goal

Maintain minimal operational cost while preserving output quality.

## LLM Strategy

* Batch multiple tickers
* Use smallest viable model
* Reduce prompt size aggressively
* Avoid redundant calls
* Committee roles default to the configured `economy` profile
* Only escalated `risk_manager`, `macro_strategist`, and `pm` rerun with the configured `deep` profile

## BudgetGuard

`config/models.yaml` defines a `budget_guard` block for optional expensive LLM paths.

Current guarded paths:

* `ensemble_deep`
* `ensemble_tie_break`
* `committee_deep`
* `macro_narrative`
* `policy_impact`

Current default mode is `shadow`. In shadow mode, BudgetGuard estimates incremental cost, records a `budget_guard_decision` pipeline event, and reports whether the daily cap would have blocked the path, but it does not skip the LLM call. This keeps cost-risk visibility high without changing official output behavior.

`enforce` mode is reserved for a later operational decision. In enforce mode, guarded optional paths may skip deep or optional work when the estimated run cost exceeds `daily_cap_usd`.

`output/data/cost_log.json` includes BudgetGuard decision counts, guarded path outcomes, profile counts, and total estimated incremental guarded cost. This is telemetry only; it is not a billing ledger.

## Data Strategy

* Prefer free APIs
* Use fallback chains instead of paid redundancy

## Compute Strategy

* Avoid recomputation
* Reuse cached or stored results when valid

## Constraints

* No expensive models without explicit instruction
* No paid dependencies unless justified

## Trade-offs

* Prefer cost over marginal accuracy
* Prefer simplicity over optimization complexity
* Prefer shallow committee coverage for all tickers over deep committee coverage for a small subset
