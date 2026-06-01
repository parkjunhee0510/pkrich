# Operational Stability Expansion Design

## Status

Approved for spec writing on 2026-05-28.

## Context

The project has grown from a batch stock research automation pipeline into a broader evidence-driven research operations system. Recent work expanded search evidence, search quality gates, dashboard evidence badges, sector explorer outputs, cost telemetry, routing diagnostics, risk intelligence, and quality reliability artifacts.

The core pipeline invariant remains:

```text
collect -> analyze -> state -> output -> store -> log
```

The next expansion should not start by adding more analysis behavior. The current bottleneck is operational trust: every daily run needs a reliable way to answer whether generated outputs, web mirrors, costs, routing choices, and evidence status are internally consistent before the user relies on the research.

The accepted direction is:

```text
operational stability 60%
research quality 30%
UI consumption 10%
```

This design focuses the first expansion slice on operational stability, then connects it to research-quality telemetry and small read-only UI improvements.

## Goals

- Make daily generated output health easy to judge before adding more analysis behavior.
- Strengthen artifact, mirror, stale-file, cost, routing, and evidence diagnostics.
- Keep official decisions, output schemas, and pipeline business logic stable.
- Make provider failures, missing evidence, stale cache, and true no-evidence states distinguishable.
- Compare latest run cost against a previous comparable run instead of reading latest cost in isolation.
- Preserve the existing layer boundaries and static frontend consumption model.
- Provide enough telemetry for later BudgetGuard enforcement or evidence gate enforcement decisions without enabling them in this phase.

## Non-Goals

- Do not change official `buy` / `watch` / `avoid` behavior.
- Do not automatically delete generated artifacts.
- Do not switch BudgetGuard from `shadow` to `enforce`.
- Do not raise search provider caps.
- Do not let frontend code recompute official decisions, evidence scores, or routing results.
- Do not introduce real-time execution, trading automation, or complex infrastructure.
- Do not make schema-breaking output changes.
- Do not add a large new UI surface in the first phase.

## Accepted Approach

Use the existing `python -m src.cli.output_health_check` path as the primary operational stability gate and extend it into a richer diagnostics surface. Avoid creating a second overlapping health system unless the existing checker becomes too crowded.

The operational stability layer is observational. It reads existing artifacts and reports their health, but it does not recompute analysis, mutate decisions, call providers, update state, or change model routing.

High-level flow:

```text
output/data/*
web/public/output/data/*
logs/pipeline/*
cost_log.json
routing_outcome.json
search_evidence.json
performance_baseline.json
quality_reliability_loop.json
        |
        v
operational stability diagnostics
        |
        v
problem list / cause / recommended fix / residual risk
```

## Operational Stability Architecture

The stability layer should answer five questions for every generated run:

1. Are generated artifacts parseable and schema-compatible?
2. Do web mirrors match source artifacts byte-for-byte where expected?
3. Are any current-facing artifacts stale relative to the latest run date?
4. Did cost increase, and if so which profile or route caused it?
5. Are evidence states healthy enough to trust the recommendation context?

The layer should keep source responsibilities unchanged:

- Collector owns external provider calls and normalized evidence.
- Analyzer owns prompts, LLM calls, validation, and evidence manifests.
- Decision owns official actions and confidence metadata.
- Output owns deterministic artifacts and web mirror sync.
- Frontend consumes finalized JSON read-only.

## Artifact Lifecycle Policy

Generated artifacts should be classified into three groups.

### Canonical Source Artifacts

These live under `output/data` and are the source of truth for web, API, reports, and tests.

Examples:

- `index.json`
- `dashboard_history.json`
- `dashboard.json` when present
- `tickers/<TICKER>/latest.json`
- `tickers/<TICKER>/history.json`
- `sectors.json`
- `price_history.json`
- `cost_log.json`
- `routing_outcome.json`
- `search_evidence.json`
- `performance_baseline.json`
- `quality_reliability_loop.json`

Policy:

- Preserve file names and root schema contracts.
- Keep `schema_version` semantics unchanged.
- Treat manual edits as a last resort.
- Prefer source artifacts over web mirror artifacts when resolving conflicts.

### Web Mirror Artifacts

`web/public/output/data` is a static frontend mirror, not a source of truth.

Policy:

- Mirrored files must match `output/data` byte-for-byte.
- Web-only files are stale candidates unless documented as intentionally web-only.
- Legacy compatibility files should be restored from source or covered by sync policy before deletion.
- `web/dist/output/data` remains best-effort when a build output tree already exists.

### Operational/Internal Artifacts

These support diagnostics, history, cache, or auditing but are not default web mirror targets.

Examples:

- SQLite files
- `price_history.csv`
- `signal_tracker.csv`
- `routing_log.json`
- `routing_log_history.json`
- `llm_evidence/*.jsonl`
- cache files
- raw audit evidence files

Policy:

- Do not report them as mirror mismatches.
- Validate parseability or row shape where relevant.
- Do not classify large historical files as stale only because they are old.

## Stale Artifact Policy

A stale artifact is not merely old. Historical outputs are allowed to be old. A stale artifact is one whose current-facing family conflicts with the latest source run.

Example stale condition:

```text
output/data/index.json.date = 2026-05-26
output/data/dashboard_history.json latest day = 2026-05-26
web/public/output/data/dashboard.json day = 2026-04-15
```

Example non-stale historical artifacts:

```text
output/tickers/AAPL/2026-04-08.md
output/data/llm_evidence/2026-04-08.jsonl
```

Initial stale diagnostics should report candidates only. Cleanup should remain a separate explicit action.

Recommended report categories:

- `mirror_mismatch`
- `mirror_missing`
- `mirror_extra`
- `web_only_stale_candidate`
- `source_date_mismatch`
- `source_family_latest_date_mismatch`
- `expected_non_web_artifact`
- `optional_legacy_artifact_present`
- `optional_legacy_artifact_missing`

## Cost, Routing, And BudgetGuard Diagnostics

Cost health must compare the latest run against a previous comparable run. Latest-only cost does not explain whether ticker count, prompts, routing, provider calls, or deep review caused a change.

Required cost diagnostics:

- latest run date and comparable run date
- total cost delta and percentage delta
- estimated monthly cost
- monthly budget usage ratio
- profile-level call, token, and cost deltas for `economy`, `standard`, and `deep`
- calls per ticker
- cached input token ratio
- output token delta

Routing diagnostics:

- `max_daily_ensemble`
- `eligible_count`
- `selected_count`
- `skipped_due_to_cap_count`
- `conflicted_count`
- selected tickers
- skipped tickers with priority scores when available
- router budget estimate
- deep pass cost per selected ticker
- impact of newly added tickers on deep selection

BudgetGuard diagnostics:

- mode: `off`, `shadow`, or `enforce`
- decision counts
- guarded path statuses
- `would_block_count`
- `blocked_count`
- total estimated incremental guarded cost
- paths that repeatedly would have been blocked

Policy:

- New tickers must not automatically increase `max_daily_ensemble`.
- Router output may reorder deep review priority but must not change official decisions.
- BudgetGuard `would_block` is an optimization signal, not an automatic enforcement decision.
- Enforcement should be evaluated path by path after report-only evidence exists.

## Evidence Health Diagnostics

Evidence health should distinguish operational failure from actual lack of evidence.

Required evidence diagnostics:

- provider mode: `cache` or `openai`
- candidate ticker count
- priority ticker count
- provider candidate count
- provider call count
- provider error count
- cache hit count
- stale cache hit count
- coverage ratio
- priority coverage ratio
- priority status counts
- `provider_error` versus `no_evidence` versus `not_refreshed`

Policy:

- `provider_error` is not the same as `no_evidence`.
- True no-evidence can be surfaced as a research risk.
- Router-selected tickers are good default priority evidence candidates.
- Provider caps should not be raised as part of the first stability phase.

## Research Quality Loop

Research quality is the second priority after operational stability. The quality loop should remain observational in the first phase.

Flow:

```text
router-selected tickers
      |
      v
priority evidence refresh
      |
      v
search_evidence status
      |
      v
search audit / risk intel / quality metrics
      |
      v
confidence metadata / dashboard badges / admin warnings
```

Principles:

- Refresh important evidence first instead of spreading provider cost equally across all tickers.
- Preserve provider failure as an operational issue.
- Keep search-quality gates in shadow/report mode until there is enough evidence to enforce.
- Use search audit to detect claim-evidence mismatch, not to create official actions.
- Keep risk intelligence as a read-only explanation layer.

Initial research-quality improvements:

- Clarify provider error causes and cache fallback status.
- Improve priority ticker evidence coverage from zero or unknown states.
- Make `no_evidence`, `not_refreshed`, `provider_error`, `cache_hit`, and `stale_cache_hit` visible in reports.
- Connect search audit issue counts to confidence metadata as observational context.

## UI Consumption Scope

UI work should be small and read-only in the first phase. It should consume finalized artifacts and avoid recomputing decisions or scores.

### Admin

Admin is the main operating-status surface.

Candidate fields:

- latest run date
- output health status
- mirror mismatch count
- stale candidate count
- monthly budget usage
- BudgetGuard would-block paths
- search evidence provider status
- priority coverage ratio
- provider error count

### Dashboard

Dashboard should show only compact trust signals.

Candidate fields:

- evidence status badge
- provider error versus no evidence versus covered
- stale run warning only when present
- priority ticker evidence state

### TickerDetail

TickerDetail should explain ticker-level evidence.

Candidate fields:

- search evidence summary
- search audit issue summary
- related risk intelligence alerts
- data freshness
- wording that says evidence refresh failed when status is `provider_error`

UI rules:

- Read finalized JSON as-is.
- Do not recompute official decisions.
- Do not recompute evidence score.
- Do not recalculate cost or routing.
- Keep loading, empty, error, focus, mobile touch target, and contrast standards from the existing UI quality work.

## Phase Plan

### Phase 1: Operational Stability Core

- Extend output health diagnostics for mirror, stale, optional legacy, and non-web artifact categories.
- Add comparable-run cost diagnostics.
- Add routing cap and new-ticker impact diagnostics.
- Add evidence status diagnostics.
- Keep cleanup manual and explicit.

### Phase 2: Research Quality Recovery

- Improve priority evidence status reporting.
- Distinguish provider failure, no evidence, stale cache, and not refreshed consistently.
- Strengthen search audit and risk-intel reporting as observational context.
- Keep official decision behavior unchanged.

### Phase 3: Minimal UI Consumption

- Add compact operational summary to Admin.
- Add stale/evidence warning surfaces to Dashboard only when needed.
- Add ticker-level evidence status wording to TickerDetail.
- Keep frontend read-only over finalized artifacts.

## Testing Strategy

Always run:

```bash
python -m compileall main.py src tests
python -m src.cli.output_health_check
```

Backend and output tests:

- `tests/test_output_health_check.py`
- `tests/test_output_schema.py`
- `tests/test_output.py`
- `tests/test_performance_output.py`
- `tests/test_performance_metrics.py`
- `tests/test_cost_log_output.py`
- `tests/test_routing_outcome_output.py`

Pipeline and evidence tests:

- `tests/test_search_evidence.py`
- `tests/test_search_evidence_config.py`
- `tests/test_search_evidence_priority.py`
- `tests/test_search_quality_gate.py`
- `tests/test_pipeline_quality_wiring.py`

Ticker and sector tests when watchlist or sector artifacts are involved:

- `tests/test_config.py`
- `tests/test_sector_scan.py`
- `tests/test_run_sectors_cli.py`

Frontend checks when UI files are touched:

- `npm run lint`
- `npm run build`
- relevant component or utility tests
- browser smoke checks for Admin, Dashboard, and TickerDetail when visual behavior changes

## Documentation Updates

Implementation should update the relevant docs when behavior changes:

- `docs/output.md` for artifact family, mirror, stale, and optional legacy policies
- `docs/cost.md` for cost health, BudgetGuard review, and profile deltas
- `docs/data-collection.md` for search evidence provider status semantics
- `docs/testing.md` for operational stability verification commands

Docs are not required for purely internal refactors that do not change behavior, contracts, routing, or output shape.

## Completion Criteria

The first implementation slice is complete when:

- operational health reports classify artifact, mirror, stale, cost, routing, BudgetGuard, and evidence issues clearly
- generated output and web mirror checks remain byte-for-byte strict for mirrored files
- stale candidates are reported without automatic deletion
- provider failure and true no-evidence are distinguishable in diagnostics
- comparable-run cost deltas are visible by profile
- new ticker artifact completeness can be checked
- official decisions, output schema, and business logic are unchanged
- relevant tests and compile checks pass

## Risks And Mitigations

- Risk: Health checks become too broad and hard to maintain.
  Mitigation: Keep checks modular by artifact family and issue code.

- Risk: Stale detection marks valid historical files as problems.
  Mitigation: Only compare current-facing artifact families and maintain explicit historical exemptions.

- Risk: Cost optimization harms analysis quality.
  Mitigation: Keep first-phase changes observational unless a config-only optimization has clear tests and a limited blast radius.

- Risk: Provider failures get interpreted as weak ticker evidence.
  Mitigation: Preserve separate status values for provider failure, no evidence, not refreshed, cache hit, and stale cache.

- Risk: UI starts recomputing backend logic.
  Mitigation: UI consumes finalized artifacts only and shows compact status metadata.
