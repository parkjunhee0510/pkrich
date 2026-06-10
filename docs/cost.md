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
* `search_evidence`

Current default mode is `shadow`. In shadow mode, BudgetGuard estimates incremental cost, records a `budget_guard_decision` pipeline event, and reports whether the daily cap would have blocked the path, but it does not skip the LLM call. This keeps cost-risk visibility high without changing official output behavior.

`enforce` mode is reserved for a later operational decision. In enforce mode, guarded optional paths may skip deep or optional work when the estimated run cost exceeds `daily_cap_usd`.

`output/data/cost_log.json` includes BudgetGuard decision counts, guarded path outcomes, profile counts, total estimated incremental guarded cost, model profile cost/token/call/model counts, ensemble routing counts, and a deep-pass value summary. This is telemetry only; it is not a billing ledger. The output health check validates this minimum shape when the artifact is present so cost telemetry corruption is caught before commit.

`performance_baseline.json` derives a read-only BudgetGuard review track from the latest cost log. It uses `budget_guard.monthly_cap_usd` from `config/models.yaml` as the default monthly budget for diagnostics, and preserves decision-count and guarded-path status distributions, would-block/blocked/allow path counts, estimated incremental guarded cost, and an `enforce_review_status`. These fields are report evidence for a later operational decision; they do not switch BudgetGuard mode or skip optional LLM paths.

Operational cost health compares the latest run with a previous comparable successful run when telemetry is available. The comparison should report total cost delta, profile-level call/token/cost deltas for `economy`, `standard`, and `deep`, BudgetGuard `would_block` paths, and evidence provider call/error status. These diagnostics are warning-level by default; they do not change official decisions or automatically switch BudgetGuard to enforce mode.

Smart Model Router V1 does not increase the deep-review cap or add provider calls. It preserves the existing `max_daily_ensemble` limit and reorders eligible deep-review candidates by an explainable priority score before the existing BudgetGuard decision is recorded. Routing logs include estimated incremental and monthly deep-review cost so report-mode savings can be reviewed without switching BudgetGuard to enforce mode.

Search evidence now defaults to `openai` mode in `config/search_evidence.yaml` so priority tickers do not report zero coverage just because the local cache is empty. Provider calls are rate-limited and logged through the `search_evidence` BudgetGuard path before any live OpenAI Web Search request is attempted. Router-selected tickers are prioritized within the existing `max_search_tickers_per_run` cap, and operators can use `SEARCH_EVIDENCE_MODE=cache` for a cache-only/offline run.

## Data Strategy

* Prefer free APIs
* Use fallback chains instead of paid redundancy
* Toss Invest Open API may improve structured market-data coverage without adding LLM calls, but it is not a direct OpenAI Web Search replacement because the current Toss API document does not expose news/search endpoints
* FMP fundamentals are compacted into an LLM-facing scalar snapshot before prompt construction; raw provider payloads stay available in collected data, while noisy profile or statement attachments are excluded from prompt token estimates

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
