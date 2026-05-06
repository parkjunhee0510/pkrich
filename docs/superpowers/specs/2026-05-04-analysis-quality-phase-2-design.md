# Analysis Quality Phase 2 Design

## Summary

Phase 2 adds a shadow analytics layer for measuring analysis and decision quality without changing official recommendations.

The system will track signal performance, conviction calibration, regime-specific performance, factor attribution, and ticker-level action change reasons. The first release is observational only: `TickerDecision.action`, `TickerDecision.conviction`, and official `buy` / `watch` / `avoid` behavior remain unchanged.

This continues the Phase 1 pattern of shadow safety gates. Phase 1 added `data_quality_score` and `BudgetGuard` telemetry before enforcing behavioral changes. Phase 2 applies the same principle to analysis quality: collect evidence first, then decide later whether calibration should influence official decisions.

## Goals

- Measure whether generated actions are performing over 1d, 5d, and 20d windows.
- Compare realized outcomes by conviction bucket.
- Compare realized outcomes by market regime and action.
- Attribute later outcomes to factor signals in a transparent, non-causal way.
- Explain ticker-level action and conviction changes between runs.
- Export a stable machine-readable payload for later web and audit consumption.
- Preserve current official decision behavior.

## Non-Goals

- Do not change official `buy` / `watch` / `avoid` actions.
- Do not adjust conviction scores from historical performance yet.
- Do not add trading automation or order routing.
- Do not introduce external data fetching outside the collector layer.
- Do not make the web UI recompute performance metrics.
- Do not treat factor attribution as causal proof.

## Primary Output Contract

Add a new output artifact:

```text
output/data/analysis_performance.json
```

The root payload includes `schema_version` and is additive to existing outputs.

Proposed shape:

```json
{
  "schema_version": 1,
  "as_of": "2026-05-04",
  "summary": {
    "sample_count": 0,
    "completed_return_windows": ["1d", "5d", "20d"],
    "notes": []
  },
  "signal_performance": {},
  "conviction_calibration": {},
  "regime_performance": {},
  "factor_attribution": {},
  "action_change_reasons": []
}
```

The output layer may sync this payload into `web/public/output/data/analysis_performance.json` under the existing web mirror policy. `output/data` remains the source of truth.

## Data Sources

Phase 2 should use existing persisted and generated data:

- `signal_tracker` state for prior signals, run dates, actions, and realized return windows.
- Stored price history through the datastore/state boundary.
- Current and historical `TickerDecision` fields, including action, conviction, raw conviction, factor reasoning, and confidence metadata.
- Market regime captured during decision generation.
- Existing output history when it is already the only available source for previous decision snapshots.

The collector remains the only layer allowed to fetch external market data. Performance analytics consumes stored prices and prior outputs only.

## Layer Placement

### State

State remains responsible for updating realized return windows and triple-barrier outcome labels. Phase 2 should not duplicate price return calculations if `signal_tracker` already has the evaluated windows.

### Decision

Decision remains the owner of official actions, conviction, factor scoring, and market regime classification. Phase 2 may add comparison helpers for explaining action changes, but these helpers must not mutate `TickerDecision`.

### Utils

Shared aggregation code can live in a small utility module because it combines state rows, decision metadata, and output-facing summaries without owning official decision behavior.

Candidate module:

```text
src/utils/performance_analytics.py
```

Responsibilities:

- Normalize signal rows into performance samples.
- Group performance by action, conviction bucket, regime, and factor.
- Compute sample count, average return, median return when cheap, win rate, and triple-barrier label distributions.
- Guard against missing or incomplete return windows.

### Output

The output layer owns JSON serialization and web mirror sync.

Candidate module:

```text
src/output/analysis_performance.py
```

Responsibilities:

- Build the root `analysis_performance.json` payload.
- Include `schema_version`.
- Write deterministically sorted objects and arrays.
- Sync to web public data when the static web app exists.

## Feature Design

### 1. Signal Performance Tracking

Signal performance groups realized returns by official action.

Metrics per action and window:

- `sample_count`
- `completed_count`
- `avg_return`
- `median_return`
- `win_rate`
- `loss_rate`
- `missing_count`
- `triple_barrier_outcomes`

Action-specific win semantics:

- `buy`: a positive realized return is a win.
- `avoid`: a non-positive realized return is a win because the system avoided downside.
- `watch`: no directional win rate should be overclaimed; report positive, negative, and flat distribution instead.

This avoids making watch look like a directional trade recommendation.

### 2. Conviction Calibration

Conviction calibration groups completed outcomes by conviction bucket.

Initial buckets:

- `0_35`
- `35_50`
- `50_65`
- `65_80`
- `80_100`

Per bucket metrics:

- `sample_count`
- `action_counts`
- `avg_return_1d`
- `avg_return_5d`
- `avg_return_20d`
- `buy_win_rate`
- `avoid_win_rate`

The first release must label this section as observational. It should not emit recommended calibration changes such as "lower threshold" or "raise threshold" because sample size will often be too small.

### 3. Regime-Specific Performance

Regime performance groups outcomes by market regime and action.

Expected keys:

- `regime`
- `action`
- `sample_count`
- `avg_return_1d`
- `avg_return_5d`
- `avg_return_20d`
- `win_rate`
- `triple_barrier_outcomes`

The grouping should support known regime strings from `MarketRegime.regime` and tolerate unknown legacy strings by grouping them under their raw normalized value. Missing regime values should become `unknown`.

### 4. Factor Attribution

Factor attribution summarizes how factor signals co-occurred with later outcomes.

This is not causal attribution. The payload should call it `factor_attribution` for user familiarity, but docs and labels should describe it as "observed association" rather than causal proof.

Initial factor inputs:

- `TickerDecision.factor_reasoning`
- `TickerDecision.factors`
- factor score payloads already emitted by the decision layer

Per factor metrics:

- `sample_count`
- `avg_score`
- `positive_score_count`
- `negative_score_count`
- `avg_forward_return_5d`
- `avg_forward_return_20d`
- `best_action_context`
- `worst_action_context`

If a factor is missing for a ticker or historical row, the aggregator skips that factor for that sample and increments a top-level missing-factor count.

### 5. Ticker Action Change Reason

Action change reasons compare the latest decision for each ticker with the previous available decision snapshot.

Candidate module:

```text
src/decision/action_change_reason.py
```

Each reason payload:

```json
{
  "ticker": "AAPL",
  "previous_action": "watch",
  "current_action": "buy",
  "previous_conviction": 58,
  "current_conviction": 68,
  "reason_codes": ["action_upgraded", "conviction_crossed_buy_threshold"],
  "summary": "watch -> buy because conviction crossed the buy threshold.",
  "contributors": []
}
```

Initial reason codes:

- `new_ticker`
- `action_upgraded`
- `action_downgraded`
- `action_unchanged`
- `conviction_increased`
- `conviction_decreased`
- `conviction_crossed_buy_threshold`
- `conviction_fell_below_buy_threshold`
- `conviction_crossed_avoid_threshold`
- `conviction_recovered_from_avoid_threshold`
- `macro_regime_changed`
- `top_factor_changed`
- `data_quality_improved`
- `data_quality_deteriorated`
- `insufficient_previous_snapshot`

Summaries should be deterministic and template-based. No LLM call is needed.

## Data Flow

The runtime flow stays aligned with the repository invariant:

```text
collect -> analyze -> state -> output -> store -> log
```

Phase 2 fits after decisions and state refresh have produced current decisions and updated historical return windows:

```text
prior signal history + stored prices
current decisions + current regime + factor metadata
-> performance analytics aggregation
-> output/data/analysis_performance.json
-> optional web/public mirror
```

The analytics payload is a downstream artifact. It must not feed back into the same run's official decision calculation.

## Error Handling

- Missing history should produce empty metric groups with `sample_count: 0`, not fail the pipeline.
- Missing return windows should increment `missing_count` and exclude the sample from completed-window averages.
- Unknown actions should be grouped under `unknown`.
- Unknown regimes should be grouped under normalized raw regime text or `unknown`.
- Malformed factor payloads should be skipped and counted.
- Output write failure should follow existing output-layer behavior and log a warning where practical.

## Testing Strategy

Unit tests:

- Signal performance computes action-level averages and win semantics for buy, avoid, and watch.
- Conviction bucket boundaries are stable.
- Regime performance groups by regime and action.
- Factor attribution skips missing factors and aggregates available factors.
- Action change reason detects upgrades, downgrades, threshold crossings, and data-quality shifts.

Output tests:

- `analysis_performance.json` includes `schema_version`.
- Shape snapshot covers the top-level contract.
- Empty history produces a valid empty payload.

Integration-focused tests:

- A small synthetic run with two tickers and prior signal rows produces all five Phase 2 sections.
- Existing decision behavior is unchanged when performance analytics is generated.

## Rollout

Phase 2 should ship in two implementation slices:

1. Backend analytics and output JSON.
2. Optional frontend/dashboard consumption after the output contract is stable.

The first implementation should not add visible web UI unless explicitly requested. It should make the data available to the frontend through the new JSON artifact.

## Acceptance Criteria

- `output/data/analysis_performance.json` is generated with `schema_version`.
- Signal performance includes action-level 1d, 5d, and 20d metrics when completed samples exist.
- Conviction calibration is present and observational.
- Regime performance is grouped by regime and action.
- Factor attribution is present and clearly non-causal.
- Ticker action change reasons are deterministic and do not use LLM calls.
- Official decisions and convictions are unchanged by this feature.
- Relevant docs are updated.
- Focused tests and `python -m compileall main.py src tests` pass.

## Risks And Mitigations

### Small Sample Overinterpretation

Risk: early performance metrics may look authoritative despite low sample counts.

Mitigation: include `sample_count`, keep calibration observational, and avoid recommendation language.

### Watch Action Misread As A Trade

Risk: watch win rate could be interpreted as directional performance.

Mitigation: report watch distributions instead of directional win rate.

### Factor Attribution Overclaimed As Causal

Risk: factor associations could be mistaken for causal explanation.

Mitigation: document the section as observed association and avoid causal wording in generated summaries.

### Historical Shape Drift

Risk: older output rows may not have all decision metadata.

Mitigation: tolerate missing fields, use defensive normalization, and count missing values.

### Feedback Loop Into Decisions

Risk: performance analytics could accidentally affect same-run official actions.

Mitigation: keep Phase 2 output-only, avoid changing decision thresholds, and test that generated actions are unchanged.
