# Quality Reliability Loop V1 Design

## Status

Approved for spec review on 2026-05-21.

## Context

The stock research pipeline is already a mature batch workflow:

```text
collect -> analyze -> state -> output -> store -> log
```

Recent work has expanded sector coverage, search evidence, dashboard JSON, output health checks, and transient file-write retries. The project also already has several related designs:

- `2026-05-04-analysis-quality-phase-2-design.md`
- `2026-05-06-pipeline-runtime-speed-design.md`
- `2026-05-12-performance-200-masterplan-design.md`
- `2026-05-07-openai-web-search-evidence-design.md`
- `2026-05-19-risk-intelligence-graph-design.md`

This design intentionally does not replace those plans. It turns the most useful parts of them into a focused first implementation slice: a daily quality and reliability loop that measures whether the system is improving and whether its outputs can be trusted.

The user explicitly approved relaxing the cost limit for this expansion. Therefore V1 does not treat monthly cost as a hard blocker. Cost remains an important telemetry dimension, but not a constrai  nt that should prevent useful quality work in this phase.

## Goals

- Measure decision quality without changing official actions.
- Track whether generated signals perform over 1d, 5d, and 20d windows when data exists.
- Summarize conviction calibration and signal outcomes without overstating small samples.
- Combine reliability, quality, evidence, and cost telemetry into a single operating loop.
- Detect broken or malformed generated JSON as a high-priority reliability issue.
- Produce machine-readable artifacts that the web dashboard can consume later.
- Produce a concise human-readable performance report for daily review.
- Preserve the existing pipeline invariant and layer boundaries.

## Non-Goals

- Do not change official `buy` / `watch` / `avoid` behavior in V1.
- Do not automatically change factor weights, thresholds, or portfolio actions.
- Do not introduce trading automation.
- Do not move external data fetching outside the collector layer.
- Do not make the web app recompute decisions or performance metrics.
- Do not require a frontend redesign in the first slice.
- Do not block V1 purely because projected monthly cost exceeds a prior budget target.

## Cost Posture

Cost is no longer a hard constraint for this approved expansion, but it should remain visible.

V1 behavior:

- Keep collecting cost, token, call-count, model-profile, and BudgetGuard telemetry.
- Report cost increases clearly in baseline and trend artifacts.
- Do not skip quality work only because a path would have exceeded the older monthly cap.
- Do not remove BudgetGuard instrumentation because it remains useful for comparing runs.
- Prefer measurement-first changes before enabling more expensive model or search behavior.

This means V1 may prepare the project for higher-quality or premium analysis later, but the first implementation slice should still avoid adding new provider calls unless a specific subtask requires them. The reason is scope control and reproducibility, not cost avoidance.

## Accepted Approach

Implement a Quality Reliability Loop V1 as an observational layer.

The loop reads existing pipeline state and generated artifacts, computes operational metrics, writes deterministic outputs, and optionally produces a Markdown report. It does not feed back into same-run official decisions.

The design combines two priorities:

- Decision quality: Are actions, conviction buckets, and factors associated with better later outcomes?
- Reliability: Are generated artifacts parseable, complete enough, and safe for downstream use?

The loop is additive. Existing official outputs keep their current meaning.

## Architecture

### Placement

The feature lives after decision and state updates have produced the latest run data.

```text
prior signal history
+ stored price history
+ current decisions
+ cost_log
+ analysis_quality
+ search_evidence
+ output health status
-> quality reliability aggregation
-> output/data artifacts
-> optional docs/reports markdown report
```

The loop belongs primarily to `utils` and `output`:

- `utils` owns normalization, aggregation, sample-size guards, and KPI calculations.
- `output` owns deterministic serialization, report formatting, and web mirror policy.
- `decision` remains the owner of official actions and confidence metadata.
- `state` remains the owner of reproducible signal outcome records.
- `collector` remains the only layer allowed to fetch external data.

### Candidate Modules

```text
src/utils/performance_analytics.py
```

Responsibilities:

- Normalize signal tracker rows into performance samples.
- Aggregate outcomes by action, conviction bucket, regime, and factor.
- Compute reliability and quality KPIs from existing generated artifacts.
- Detect insufficient samples and missing windows.
- Avoid causal language for factor associations.

```text
src/output/performance_report.py
```

Responsibilities:

- Build JSON payloads.
- Write deterministic artifacts with stable ordering.
- Build a concise Markdown report for daily operator review.
- Reuse the existing safe JSON writer and retry behavior where applicable.

If equivalent modules already exist, implementation should extend them instead of creating duplicate paths.

## Output Contracts

V1 introduces or stabilizes the following artifacts:

```text
output/data/quality_reliability_loop.json
output/data/performance_baseline.json
output/data/performance_trends.json
output/data/analysis_performance.json
docs/reports/performance-YYYY-MM-DD.md
```

The canonical V1 artifact is:

```text
output/data/quality_reliability_loop.json
```

Proposed root shape:

```json
{
  "schema_version": 1,
  "as_of": "2026-05-21",
  "status": "ok",
  "summary": {
    "decision_quality_status": "insufficient_data",
    "artifact_reliability_status": "ok",
    "evidence_status": "partial",
    "cost_status": "reported",
    "notes": []
  },
  "decision_quality": {},
  "artifact_reliability": {},
  "evidence_quality": {},
  "cost_and_runtime": {},
  "trend_inputs": {},
  "warnings": []
}
```

Status values should be deterministic and limited to a small vocabulary:

- `ok`
- `partial`
- `warning`
- `failed`
- `insufficient_data`
- `missing`
- `reported`

Schema changes should be additive. If a field cannot be computed, emit a structured missing or insufficient-data state instead of omitting the whole section.

## Decision Quality Metrics

Decision quality is observational in V1.

Metrics should include:

- action-level realized returns over 1d, 5d, and 20d when completed
- buy win rate using positive forward return semantics
- avoid win rate using non-positive forward return semantics
- watch distribution without claiming directional win rate
- conviction bucket performance
- regime and action performance
- factor association summaries
- action change reason counts when available

Initial conviction buckets:

```text
0_35
35_50
50_65
65_80
80_100
```

Every metric group must include sample counts. When completed samples are too small, the output should say `insufficient_data` rather than imply a conclusion.

## Artifact Reliability Metrics

Artifact reliability checks whether generated outputs are safe to consume.

Required checks:

- generated operational JSON files parse successfully
- required top-level keys exist for core artifacts
- Korean strings, quotes, backslashes, and newlines serialize as valid JSON
- web-public mirrors are not treated as source of truth
- missing optional artifacts are reported without crashing the loop

JSON parse failures should be treated as P0 for this feature because later performance work cannot be trusted if the evidence artifacts are malformed.

The existing `src.cli.output_health_check` should be expanded or reused so the reliability loop and health check agree on core artifact expectations.

## Evidence Quality Metrics

Evidence quality summarizes search and supporting evidence status without changing official actions.

Metrics should include:

- evidence coverage by ticker
- searched or refreshed ticker count
- stale evidence count
- provider unavailable count
- malformed cache count
- priority-for-refresh count when available
- weak-evidence buy count in shadow/report mode

Operational failures such as provider unavailable or not refreshed should be distinct from a true no-evidence result.

## Cost And Runtime Metrics

Because the user relaxed the cost limit, V1 should not block or suppress output based on cost. It should report:

- estimated run cost when available
- LLM calls per ticker
- token counts by profile
- BudgetGuard allow / would-block / blocked counts
- optional deep path usage
- search evidence provider usage
- runtime stage durations when logs expose them

Cost status should be `reported` unless the cost artifact itself is missing or malformed.

## Markdown Report

The optional Markdown report should be concise and operator-focused.

Suggested sections:

- Today's Status
- Decision Quality
- Artifact Reliability
- Evidence Quality
- Cost And Runtime
- Warnings
- Next Review Items

The report should not recommend trades. It should describe system quality and evidence state.

## Data Flow

V1 consumes existing state and output artifacts:

```text
signal_tracker state
stored prices
latest decisions
analysis_quality.json
cost_log.json
search_evidence.json
search_audit.json
dashboard_history.json
pipeline logs
output health results
```

It produces:

```text
quality_reliability_loop.json
performance_baseline.json
performance_trends.json
analysis_performance.json
performance-YYYY-MM-DD.md
```

The generated JSON artifacts remain the source of truth for the web app. Markdown is a human-facing summary.

## Error Handling

- Missing signal history produces empty metric groups with `sample_count: 0`.
- Missing return windows increment `missing_count`.
- Unknown actions are grouped under `unknown`.
- Unknown regimes are normalized to raw lowercase text or `unknown`.
- Malformed factor payloads are skipped and counted.
- Missing optional artifacts are represented as `missing`.
- Malformed core JSON artifacts mark artifact reliability as `failed`.
- Output write errors use existing safe write and retry helpers where practical.
- The loop should not mutate official decisions even when metrics look poor.

## Testing Strategy

Unit tests:

- action-level performance aggregation handles buy, avoid, and watch semantics
- conviction bucket boundaries are stable
- insufficient samples produce `insufficient_data`
- malformed factor payloads are counted without crashing
- artifact reliability catches malformed JSON
- missing optional artifacts produce structured missing states
- cost status remains report-only and does not block output

Output tests:

- `quality_reliability_loop.json` includes `schema_version`
- generated JSON is parseable with Korean text and special characters
- deterministic output ordering is stable
- output health check covers the new canonical artifact

Integration-focused tests:

- a synthetic run with prior signals and current decisions produces decision quality sections
- malformed generated JSON is detected before success is claimed
- official decision actions remain unchanged when the loop runs

Baseline verification commands:

```powershell
python -m unittest discover -s tests -v
python -m compileall main.py src tests
python -m src.cli.output_health_check
```

If the first implementation slice is intentionally smaller, run focused tests plus compile and health check:

```powershell
python -m unittest tests.test_output tests.test_output_health_check -v
python -m compileall main.py src tests
python -m src.cli.output_health_check
```

## Rollout

### Slice 1: Canonical Quality Loop Artifact

- Build or extend analytics helpers.
- Emit `quality_reliability_loop.json`.
- Cover malformed and missing artifact behavior with tests.
- Preserve official decisions.

### Slice 2: Baseline And Trends

- Populate `performance_baseline.json`.
- Populate `performance_trends.json`.
- Add trend comparison across available historical runs.

### Slice 3: Human Report

- Generate `docs/reports/performance-YYYY-MM-DD.md`.
- Keep the report concise and focused on system quality.

### Slice 4: Dashboard Consumption

- Expose the canonical artifact to `web/public/output/data`.
- Add frontend consumption only after the JSON contract is stable.

## Acceptance Criteria

- `output/data/quality_reliability_loop.json` is generated with `schema_version: 1`.
- Official `TickerDecision.action` and `TickerDecision.conviction` are unchanged by V1.
- Decision quality metrics include sample counts and insufficient-data states.
- Core JSON artifact parse failures are detected and reported.
- Cost is reported but does not block the loop.
- Search evidence status distinguishes operational gaps from true no-evidence results.
- Output health checks include the new canonical artifact when generated.
- Relevant docs are updated when implementation changes behavior, contracts, or outputs.
- Focused tests, compile checks, and output health checks pass before completion.

## Risks And Mitigations

### Small Sample Overinterpretation

Risk: Early decision quality metrics may look more authoritative than they are.

Mitigation: include sample counts, use `insufficient_data`, and avoid recommendation language.

### Metric Sprawl

Risk: The loop could become a large dashboard backend before its core contract is stable.

Mitigation: make `quality_reliability_loop.json` the canonical V1 artifact and defer frontend work.

### Artifact Shape Drift

Risk: Existing generated artifacts may have inconsistent historical shapes.

Mitigation: normalize defensively, count missing fields, and keep schema changes additive.

### Cost Drift Without Guardrails

Risk: Relaxed cost constraints may make later premium analysis harder to reason about.

Mitigation: keep cost telemetry visible and trendable even when it is not a blocker.

### Layer Boundary Drift

Risk: Performance analytics could accidentally change decision behavior.

Mitigation: keep V1 observational, keep official decisions in `decision`, and test that actions remain unchanged.
