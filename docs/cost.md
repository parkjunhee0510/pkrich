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
