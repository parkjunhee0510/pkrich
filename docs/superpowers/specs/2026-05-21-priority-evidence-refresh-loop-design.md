# Priority Evidence Refresh Loop V1 Design

## Context

The project now has a working performance measurement path and a canonical
`output/data/quality_reliability_loop.json` artifact. The latest quality loop
shows that decision quality and artifact reliability are operational, while
search evidence remains the weak point:

- `decision_quality_status`: `ok`
- `artifact_reliability_status`: `ok`
- `cost_status`: `reported`
- `evidence_status`: `partial`

The current `performance_baseline.json` evidence block reports zero evidence
coverage across the watchlist and zero priority coverage:

- `ticker_count`: 23
- `covered_ticker_count`: 0
- `coverage_ratio`: 0.0
- `priority_ticker_count`: 5
- `priority_covered_ticker_count`: 0
- `provider`: `cache`
- `searched_ticker_count`: 0
- `status_counts.no_evidence`: 23

This design turns that observed gap into the next controlled improvement slice.

## Goal

Improve recommendation reliability by restoring search evidence coverage for
the highest-value tickers first.

V1 must explain why each priority ticker was selected for evidence refresh,
attempt refresh in priority order when live search mode is enabled, and record
whether the result was real evidence, true no-evidence, a cache state, a cap
skip, or a provider failure.

## Non-Goals

- Do not change official `buy` / `watch` / `avoid` actions.
- Do not enable search-evidence gate enforcement.
- Do not make frontend code recompute evidence quality or official decisions.
- Do not create a separate provider pipeline outside the collector boundary.
- Do not raise `max_search_tickers_per_run` as part of this design.
- Do not make cache mode call live providers.

## Approved Priority Definition

V1 uses Smart Model Router `selected_tickers` as the default priority pool.

This keeps the first implementation aligned with existing routing telemetry:
the router already selects tickers where additional intelligence is likely to
matter, then the pipeline passes those tickers to the search evidence collector
as `priority_tickers`.

The refresh order must apply evidence-specific ordering inside that pool.
Tickers with these signals move earlier:

- `no_evidence`
- `not_refreshed`
- stale cache
- current portfolio holding
- important official action, meaning `buy` or `avoid`
- high volatility when available

The intent is to keep Smart Router as the broad value selector while making
the collector refresh order better reflect evidence gaps.

## Current Data Flow

```text
AnalysisEnsemble
  -> Smart Model Router
  -> diagnostics.selected_tickers
  -> pipeline._routing_priority_tickers(...)
  -> collect_search_evidence(..., priority_tickers=...)
  -> output/data/search_evidence.json
  -> output/data/performance_baseline.json
  -> output/data/quality_reliability_loop.json
```

## Proposed V1 Data Flow

```text
AnalysisEnsemble
  -> Smart Model Router selected_tickers
  -> evidence refresh priority builder
  -> collect_search_evidence(..., priority_tickers=ordered_priority_tickers)
  -> search_evidence.json with priority reasons
  -> performance_baseline.json with priority evidence counters
  -> quality_reliability_loop.json with specific evidence warnings
```

## Components

### 1. Evidence Refresh Priority Builder

The builder is deterministic and side-effect free.

Inputs:

- router-selected tickers
- full run ticker set
- existing normalized search evidence payload or cache-derived status
- current decisions, including action and confidence metadata when available
- portfolio holding membership when available
- collected ticker data when high-volatility context is available

Outputs:

- ordered priority ticker list
- per-ticker refresh reason codes
- summary reason counts

Initial reason code vocabulary:

- `router_selected`
- `no_evidence`
- `not_refreshed`
- `stale_cache`
- `portfolio_holding`
- `important_action`
- `high_volatility`

The builder must preserve router order as a tie-breaker so output remains
deterministic.

### 2. Collector Integration

`collect_search_evidence(..., priority_tickers=...)` remains the provider
boundary. Analyzer, decision, output, and web code must not call web search
directly.

Cache mode behavior:

- No live provider calls.
- Priority metadata is still written.
- Priority tickers without usable cache must remain distinguishable as
  `not_refreshed`, `no_evidence`, or cache-related statuses according to the
  existing collector semantics.

OpenAI mode behavior:

- Refresh priority tickers before the rest of the candidate set.
- Apply the existing `max_search_tickers_per_run` cap after ordering.
- Apply the existing per-ticker query cap.
- Record provider errors separately from true no-evidence results.
- Keep BudgetGuard reporting in the existing guarded `search_evidence` path.

### 3. Output And Telemetry

`search_evidence.json` remains the source of truth for normalized search
evidence status. V1 adds or formalizes these fields:

- `run_summary.priority_tickers`
- `run_summary.priority_ticker_count`
- `run_summary.priority_refresh_reasons`
- `run_summary.priority_status_counts`
- `by_ticker[TICKER].priority_for_refresh`
- `by_ticker[TICKER].priority_refresh_reasons`

`performance_baseline.json` continues to derive read-only evidence metrics
from `search_evidence.json`. V1 adds:

- `priority_refresh_candidate_count`
- `priority_provider_error_count`
- `priority_not_refreshed_count`
- `priority_no_evidence_count`

`quality_reliability_loop.json` turns priority evidence gaps into specific
warning codes. The V1 warning code vocabulary includes:

- `priority_evidence_not_refreshed`
- `priority_evidence_provider_error`
- `priority_evidence_zero_coverage`
- `priority_evidence_stale_cache`

These are operational diagnostics only. They must not alter official actions,
model routing, factor weights, or frontend behavior.

## Evidence Status Semantics

V1 must keep operational gaps separate from true no-evidence results.

Supported status meanings:

- `covered`: usable evidence exists.
- `no_evidence`: provider ran successfully, but no usable evidence was found.
- `not_refreshed`: ticker was not refreshed in this run because of mode, cap,
  or ordering.
- `stale_cache`: older cache was reused and is still visible as stale.
- `provider_unavailable`: provider could not be used because of key, config,
  or availability.
- `provider_error`: provider call failed.
- `cache_error`: cache read or write failed.

Provider failures must not be collapsed into `no_evidence`.

## Error Handling

- Search evidence failures must not crash the full daily pipeline.
- Failures must be recorded in `search_evidence.json`, pipeline events, and
  downstream performance artifacts when possible.
- A provider error must make the evidence loop less healthy, but it must
  not imply that a ticker truly lacks evidence.
- Cache mode must be explicit, not ambiguous. If live calls are skipped
  because the mode is `cache`, that must be visible in status or summary
  telemetry.
- Health checks must reject malformed priority metadata while accepting valid
  empty or cache-only telemetry.

## Testing Strategy

Tests must avoid real provider calls.

Required coverage:

- Smart Router selected tickers become the priority pool.
- Existing evidence states reorder refresh priority as expected.
- Portfolio holdings and `buy` / `avoid` actions produce reason codes.
- Cache mode writes priority metadata without provider calls.
- Mock OpenAI mode calls tickers in priority order within the configured cap.
- Provider errors and true no-evidence results produce different statuses.
- Output health checks validate the minimum shape of new priority fields.
- `quality_reliability_loop.json` reflects priority evidence status through
  warning codes.

## Success Criteria

V1 is complete when:

- Each priority ticker has machine-readable refresh reason codes.
- Cache-only runs explain why priority evidence coverage is still zero.
- Live search validation runs refresh priority tickers before non-priority
  tickers and stay inside the configured cap.
- Provider failures, cap skips, stale cache, and true no-evidence results are
  distinguishable.
- `performance_baseline.json` and `quality_reliability_loop.json` expose
  priority evidence health without changing decisions.
- `python -m src.cli.output_health_check` passes after artifact generation.

## Risks And Mitigations

Risk: Deep-review priority and evidence-refresh priority are not identical.

Mitigation: Use Smart Router `selected_tickers` as the V1 priority pool, but
apply evidence-specific ordering inside that pool. This keeps scope small while
making the evidence path more accurate.

Risk: Cache mode can look like true no-evidence.

Mitigation: Preserve `not_refreshed`, stale-cache, provider, and cache status
fields so cache-only behavior is visible.

Risk: Provider failures could be misread as weak ticker evidence.

Mitigation: Keep `provider_error` and `provider_unavailable` distinct from
`no_evidence`, and ensure decision-layer search quality treats operational
gaps as unavailable evidence rather than a low-quality evidence verdict.

Risk: More fields could make output contracts noisy.

Mitigation: Add backward-compatible fields only, keep them under existing
`search_evidence`, `performance_baseline`, and `quality_reliability_loop`
contracts, and validate minimum shape through output health checks.

## Implementation Boundary

This design is a collector/output/telemetry improvement. It can touch pipeline
wiring where priority tickers are prepared, but it must not move provider calls
outside the collector, and it must not change official decision generation.
