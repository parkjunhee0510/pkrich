# Pipeline Contract Hardening Design

## Summary

This design tightens the pipeline contract around five related areas:

1. Add and document consistent output `schema_version` usage.
2. Clarify the real State/Decision execution order.
3. Add an explicit `data_quality_score` that can feed decision confidence.
4. Add a `BudgetGuard` contract for pre-call LLM cost governance.
5. Document the `web/public` and `web/dist` sync policy.

The recommended implementation is contract-first and conservative. It should expose quality and budget decisions, preserve existing output compatibility, and avoid abrupt action changes unless an explicit enforcement flag is enabled later.

## Goals

- Make machine-readable output contracts easier to reason about.
- Align documentation with the actual `src/pipeline.py` execution order.
- Give the decision layer a clearer data-quality signal without making the LLM or output layer the source of truth.
- Add a pre-call budget guard model that complements the existing cost logs.
- Make static web sync behavior deterministic, documented, and easy to test.
- Keep official `buy` / `watch` / `avoid` decisions owned by the rule-based decision layer.

## Non-Goals

- Do not replace the rule-based decision layer with LLM output.
- Do not introduce trading automation or real-time systems.
- Do not make the web app recompute decisions or pipeline logic.
- Do not make initial data-quality enforcement silently downgrade official actions without an auditable flag.
- Do not raise the monthly LLM budget.
- Do not rewrite all output sync helpers in one large refactor unless required for correctness.

## Existing Context

### Current Pipeline

The root invariant is:

```text
collect -> analyze -> state -> output -> store -> log
```

The concrete `run_pipeline()` path is more detailed:

```text
collect market/news/macro/context
-> detect market regime and attach run-level macro context
-> analyze with economy/deep/tie-break consensus
-> attach committee analysis
-> update prior signal returns and triple-barrier labels
-> load signal stats
-> run policy impact stage
-> generate decisions
-> record new signals
-> reload signal stats
-> write markdown/json/web-facing outputs
-> write auxiliary outputs and notifications
-> record analysis run
-> finalize logs and operational reports
```

This means State appears in two roles:

- Pre-decision state refresh: old signal outcomes and stats become decision inputs.
- Post-decision state write: new decisions are recorded as signals for future runs.

### Current Schema Versioning

`src/output/schema.py` defines:

```python
SCHEMA_VERSION = 1
```

Several JSON outputs already include it, including sharded dashboard outputs, `analysis_quality.json`, `api_status.json`, `cost_log.json`, and `routing_outcome.json`. The missing piece is a clear rule that this is the output consumer contract version and should appear on all root machine-readable JSON payloads unless intentionally excluded.

### Current Data Quality

`src/decision/confidence.py` already calculates `data_quality` as part of `confidence_meta`. Today it mainly uses analyzer quality information such as missing critical fields, validation warnings, fallback usage, and encoding issues.

This design expands that concept into an explicit `data_quality_score` with component-level detail. The existing `data_quality` field can remain as an alias or final score for compatibility.

### Current Cost Control

Cost control currently exists through:

- `config/models.yaml` model profiles and estimates
- token-budget helpers
- analyzer retry budgets
- ensemble caps
- committee economy/deep routing
- `logs/pipeline/*.jsonl`
- `output/data/cost_log.json`

This is mostly configuration plus post-run reporting. A `BudgetGuard` should add a pre-call decision point before optional or expensive LLM calls.

### Current Web Sync

`output/data` is the source of truth. Some output writers sync selected files to `web/public/output/data`, and the main JSON export helper also syncs to `web/dist/output/data` when a build output tree exists.

The behavior is useful but scattered. This design documents a policy first and only consolidates helpers where it reduces risk.

## Recommended Architecture

### 1. Output Schema Version Contract

### Contract

`src/output/schema.py::SCHEMA_VERSION` remains the single output schema version constant.

Every root JSON payload intended for machine consumption should include:

```json
{
  "schema_version": 1
}
```

This includes:

- Dashboard index and history payloads
- Sharded ticker latest/history payloads
- Operational payloads such as API status, analysis quality, cost log, routing outcome, direction alignment, sector scan, factor audit, signal quality, policy impact, tuning report, and validation warnings
- Audit JSON payloads when the output is a durable contract

Intentional exceptions should be documented. Examples:

- JSONL evidence manifests may include per-record `schema_version` rather than a root field.
- Imported third-party cache files do not need to be upgraded to the output schema contract.
- Legacy compatibility payloads may keep their existing shape during rollout if adding a root field would break a known consumer.

### Semantics

`schema_version` means "consumer-facing output shape version." It does not mean:

- pipeline algorithm version
- model version
- prompt version
- run version
- data freshness version

When a backward-compatible field is added, `SCHEMA_VERSION` does not need to change. It should change only when consumers must handle a shape migration or a meaningfully changed contract.

### Tests

Use focused output schema tests:

- Assert important root payloads include `schema_version`.
- Keep snapshot shape tests updated only when the shape intentionally changes.
- Add regression coverage for any newly versioned output.

### 2. State/Decision Execution Order

### Documentation Model

Keep the compact root invariant:

```text
collect -> analyze -> state -> output -> store -> log
```

Clarify the concrete decision path:

```text
collect
-> detect market regime and macro context
-> analyze
-> pre-decision state refresh
   - update realized returns for prior signals
   - update triple-barrier labels
   - load signal_stats
-> decision
   - consume market regime detected earlier in the run
   - score factors
   - apply confidence metadata
   - generate official action
-> post-decision state write
   - record_signals with decisions
   - reload signal_stats for output
-> output
-> store
-> log
```

### Ownership

- State owns reproducible derived history and signal records.
- Decision owns factor scoring, conviction, confidence adjustment, and official action.
- Output serializes decisions and state-derived summaries but does not recompute them.
- Datastore remains the persistence boundary.

### Important Nuance

The decision layer may consume state, but it does not write state. `run_pipeline()` coordinates the state writes before and after decision generation through datastore/state utilities.

### 3. Data Quality Score

### Contract

Add an explicit `data_quality_score` that is calculated before or during decision confidence evaluation and is serialized under decision confidence metadata.

Recommended initial output:

```json
{
  "decision": {
    "confidence_meta": {
      "data_quality": 0.74,
      "data_quality_score": 0.74,
      "data_quality_components": {
        "price_freshness": 0.9,
        "news_coverage": 0.7,
        "source_diversity": 0.8,
        "fallback_depth": 0.6,
        "missing_fundamentals": 0.75,
        "macro_context_age": 0.9,
        "analyzer_validation": 0.8
      },
      "confidence_penalty": 0.08
    }
  }
}
```

`data_quality` can remain for compatibility and should equal the final score unless a later migration separates legacy and expanded meanings.

### Inputs

The score should combine existing and newly derived signals:

| Component | Source | Meaning |
| --- | --- | --- |
| `price_freshness` | collected price/history/run date | How current the price evidence is |
| `news_coverage` | news map / analysis key news / references | Whether recent ticker evidence exists |
| `source_diversity` | news references and provider metadata | Whether sources are concentrated |
| `fallback_depth` | collector diagnostics / provider usage / fallback flags | How far down the provider chain the run had to go |
| `missing_fundamentals` | collected fundamentals / analysis fundamentals | How much valuation/fundamental data is missing |
| `macro_context_age` | macro context and market overview | Whether macro evidence is current and populated |
| `analyzer_validation` | quality summary | Existing validation, fallback, and warning signal |

### Score Shape

All components should be normalized to `0.0 <= score <= 1.0`.

Recommended first weighting:

```text
data_quality_score =
  0.25 * analyzer_validation
  0.20 * price_freshness
  0.15 * news_coverage
  0.15 * missing_fundamentals
  0.10 * source_diversity
  0.10 * fallback_depth
  0.05 * macro_context_age
```

Reasoning:

- Analyzer validation and price freshness are most important for avoiding confident but weak reports.
- News and fundamentals matter heavily for ticker decisions.
- Source diversity, fallback depth, and macro age are useful but should not dominate the first version.

### Decision Behavior

Initial mode should be conservative:

- Always compute and serialize `data_quality_score`.
- Feed it into `confidence_gate`.
- Apply conviction penalty through the existing final conviction mechanism.
- Record what an action cap would have done in metadata, but do not force action caps unless enabled.

Recommended metadata for shadow action cap:

```json
{
  "data_quality_gate": {
    "mode": "shadow",
    "threshold": 0.6,
    "max_action_if_enforced": "watch",
    "would_cap_action": true
  }
}
```

Future enforce mode:

```python
if data_quality_score < 0.6:
    max_action = "watch"
```

This enforce mode should be feature-flagged and tested before becoming default.

### Location

Recommended implementation location:

- Expand `src/decision/confidence.py` for final score and confidence metadata.
- Add a small helper module only if the component calculation becomes too large.
- Pass collector/runtime quality through `quality_summary_by_ticker` or a new `data_quality_by_ticker` map from `run_pipeline()`.

Do not put the core scoring rule in output or web code.

### 4. BudgetGuard

### Contract

Add a `BudgetGuard` that decides whether an optional paid LLM action is allowed, should be downgraded, or should be skipped.

It complements but does not replace `cost_log.json`.

### Configuration

Recommended config under `config/models.yaml`:

```yaml
budget_guard:
  mode: shadow
  daily_cap_usd: 0.25
  monthly_cap_usd: 5.00
  on_exceed: log_only
  guarded_profiles: [standard, deep]
  guarded_paths:
    - ensemble_deep
    - ensemble_tie_break
    - committee_deep
    - macro_narrative
    - policy_impact
```

Initial values should not increase cost. `shadow` mode records decisions without blocking calls.

### Modes

| Mode | Behavior |
| --- | --- |
| `off` | No budget decision is made |
| `shadow` | Estimate and log allow/deny decisions, but do not block |
| `enforce` | Apply `on_exceed` behavior |

### Exceed Behaviors

| Behavior | Meaning |
| --- | --- |
| `log_only` | Record event only |
| `skip_deep` | Skip optional deep/tie-break passes |
| `economy_only` | Downgrade optional calls to economy profile where safe |
| `abort_optional` | Skip optional paid modules, but keep core pipeline running |

Avoid aborting the full pipeline in the first version. A daily report with lower depth is better than no report when the budget cap is reached.

### Budget Events

Log one event per budget decision:

```json
{
  "component": "analyzer",
  "event": "budget_guard_decision",
  "mode": "shadow",
  "path": "ensemble_deep",
  "profile": "deep",
  "estimated_incremental_cost_usd": 0.04,
  "run_cost_so_far_usd": 0.11,
  "daily_cap_usd": 0.25,
  "decision": "allow",
  "would_block": false
}
```

### Output

Extend `cost_log.json` with a budget summary when budget events exist:

```json
{
  "budget_guard": {
    "mode": "shadow",
    "daily_cap_usd": 0.25,
    "decision_counts": {
      "allow": 5,
      "would_block": 1,
      "blocked": 0
    },
    "guarded_paths": {
      "ensemble_deep": "allow",
      "committee_deep": "would_block"
    }
  }
}
```

This is additive and should not break existing consumers.

### Location

Recommended location:

- `src/utils/budget_guard.py` for config, estimate, and decision primitives.
- Analyzer/committee/ensemble call sites ask the guard before optional expensive paths.
- `src/output/cost_log.py` summarizes logged budget events.

### 5. Web Public/Dist Sync Policy

### Source Of Truth

`output/data` is the source of truth for generated data artifacts.

### Mirrors

`web/public/output/data` is the development/static-app mirror. The frontend should read this in dev and static hosting contexts.

`web/dist/output/data` is a best-effort build-output mirror. It should be synced only when `web/dist` already exists. The pipeline should not create a full build or treat `dist` as source of truth.

### Sync Failure Behavior

Sync failures should:

- be logged as output warnings or errors
- not recompute data
- not mutate decision/state/analyzer behavior
- not fail the core pipeline unless the source output write itself failed

### Included Artifacts

Default web mirror candidates:

- dashboard/index/history payloads
- sharded ticker latest/history payloads
- API status and provider matrix
- analysis quality and validation warnings
- cost log and routing outcome
- direction alignment
- sector payloads
- backtest/factor/signal quality reports
- policy impact
- monthly/weekly summary payloads

Default exclusions:

- raw LLM evidence manifests
- raw logs
- cache databases
- SQLite files
- provider caches
- sensitive or high-volume audit internals

### Implementation Approach

First document the policy and test existing behavior. Then consolidate sync helpers only where it improves reliability.

Avoid a broad refactor that changes output timing and sync side effects at the same time.

## Rollout Plan

### Phase 1: Documentation And Contract Tests

- Update `docs/pipeline-runtime.md` with the real pre/post State and Decision order.
- Update `docs/decision.md` with `data_quality_score` ownership.
- Update `docs/output.md` with `schema_version` and web sync policy.
- Update `docs/cost.md` with the BudgetGuard contract.
- Add or adjust tests for root `schema_version` on important outputs.

### Phase 2: Data Quality Score Shadow Metadata

- Extend data-quality calculation with component scores.
- Serialize `data_quality_score`, `data_quality_components`, and `confidence_penalty`.
- Keep official action behavior compatible by default.
- Add tests for score bounds, missing data, fallback data, and metadata serialization.

### Phase 3: BudgetGuard Shadow Mode

- Add config loader and guard decision object.
- Instrument optional expensive paths in shadow mode.
- Log `budget_guard_decision` events.
- Summarize budget guard events in `cost_log.json`.
- Add tests for allow/would-block calculations and cost-log summary shape.

### Phase 4: Optional Enforcement

- Add feature flag or config mode for enforcement.
- Enable only after shadow logs prove thresholds are sensible.
- Add action-cap tests if data-quality enforcement is enabled.
- Add optional-call skip/downgrade tests if BudgetGuard enforcement is enabled.

## Backward Compatibility

- All new JSON fields are additive.
- Existing `decision.confidence_meta.data_quality` remains.
- Existing `SCHEMA_VERSION = 1` remains unless a breaking output migration is introduced.
- Existing web sync targets continue to work.
- Existing cost log fields remain stable.
- Existing official decision behavior remains unchanged in initial shadow mode.

## Test Strategy

Recommended focused tests:

- `tests/test_output_schema.py`
  - root schema version coverage
  - cost log budget summary shape
  - web public/dist sync behavior where practical
- `tests/test_decision_confidence.py`
  - component score bounds
  - missing fundamentals lowers score
  - stale or missing price lowers score
  - source diversity and news coverage behavior
- `tests/test_decision_layer.py`
  - confidence metadata includes `data_quality_score`
  - shadow gate does not alter action
  - enforce gate caps action only when enabled
- `tests/test_pipeline_quality_wiring.py`
  - pipeline passes quality/runtime summaries into decision generation
- `tests/test_model_config.py` or new `tests/test_budget_guard.py`
  - budget config defaults
  - allow/would-block decisions
  - shadow mode never blocks
  - enforce mode applies expected optional-path behavior
- `tests/test_cost_log_output.py`
  - budget guard events are summarized in `cost_log.json`

## Risks

### Over-Penalizing Sparse Tickers

Some tickers naturally have less news or fewer fundamentals. Component scoring should avoid crushing the final score just because a small-cap or ETF-like asset has limited fields.

Mitigation:

- Clamp penalties.
- Use neutral defaults where a field is not applicable.
- Record components so weak points are visible.

### Hidden Decision Changes

If `data_quality_score` feeds confidence too aggressively, official actions may change more than expected.

Mitigation:

- Start with shadow action cap.
- Keep conviction penalty modest.
- Add tests around action thresholds.
- Document rollback through existing confidence flags.

### BudgetGuard False Blocks

Bad cost estimates could skip useful deep review.

Mitigation:

- Start in `shadow`.
- Use logged actual cost to calibrate estimates.
- Prefer skipping optional depth over failing the pipeline.

### Sync Helper Drift

Multiple sync helpers may continue to diverge.

Mitigation:

- Document policy now.
- Add targeted tests.
- Consolidate helpers incrementally after behavior is protected.

## Done Criteria

- The docs describe the actual runtime order and layer ownership.
- The output schema-version policy is documented and tested for key payloads.
- `data_quality_score` is visible in decision metadata without breaking existing consumers.
- BudgetGuard has a documented contract and initial shadow-mode telemetry.
- Web sync policy identifies `output/data` as source of truth, `web/public` as mirror, and `web/dist` as best-effort mirror.
- Existing decision source-of-truth remains rule-based.
- Existing pipeline cost ceiling is not increased.
