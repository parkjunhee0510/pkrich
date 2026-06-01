# Performance 200 Masterplan Design

## Status

Approved for spec review on 2026-05-12.

## Context

The stock research pipeline is already a mature batch system with the invariant:

```text
collect -> analyze -> state -> output -> store -> log
```

It collects market, news, macro, policy, portfolio, search evidence, and peer context; runs deterministic and LLM-backed analyzer modules; generates rule-based decisions; updates signal state; writes Markdown/JSON/web artifacts; persists history; and records operational telemetry.

The current request is to raise overall system performance by roughly 200 percent. For this project, "performance" should not mean one isolated metric such as runtime, model size, or output length. It means the combined operating quality of the research system:

- reliable artifacts that can be parsed and compared between runs
- higher analysis quality with fewer validation and hallucination warnings
- better cost efficiency under a monthly budget target around USD 10
- improved signal quality measured through realized outcomes
- better evidence coverage and clearer PM-level summaries

Recent local context shows several high-leverage opportunities:

- The latest watchlist contains 23 tickers.
- The latest recorded run used 179 LLM calls.
- The latest estimated LLM/API cost was about USD 0.43 per run.
- A 20 to 22 trading-day month at that run rate is about USD 8.6 to USD 9.5.
- Recent `analysis_quality` reported 35 hallucination warnings in the latest run.
- `search_evidence.json` is currently cache-only with zero searched tickers and zero evidence coverage.
- `backtest_summary.json` and `search_audit.json` showed JSON parsing failures in the current output set.
- `BudgetGuard` reports `would_block` optional deep paths, but shadow mode still allows those paths to execute.

The accepted direction is a measurement-first balanced masterplan: restore trustworthy measurement first, then improve model routing, evidence quality, signal learning, and PM-facing consumption in controlled phases.

## Goals And Success Metrics

The goal is to make the pipeline more intelligent, cheaper per useful decision, and less fragile without breaking layer boundaries or turning the system into trading automation.

Primary success dimensions:

- Reliability: generated operational JSON artifacts are parseable and schema-stable.
- Analysis quality: hallucination, fact, consistency, and validation retry rates trend down.
- Cost efficiency: LLM calls and cost per ticker or per decision are lower or better justified.
- Signal quality: official actions can be evaluated against 1d, 5d, 20d, and triple-barrier outcomes.
- Evidence quality: important recommendations have recent, diverse, parseable evidence coverage.
- Usability: daily PM output highlights fewer, better-explained candidates.

One-month target outcomes:

- JSON parsing failures are treated as P0 and reduced to zero for generated `output/data/*.json`.
- A baseline and trend artifact exists for cost, call count, validation warnings, evidence coverage, routing value, and signal outcomes.
- LLM call reduction opportunities of 25 to 40 percent are identified or partially applied without reducing core watchlist coverage.
- A target line is established for reducing hallucination ratio by 30 to 50 percent from the baseline.
- Search evidence coverage has an operating path from zero toward 50 percent or more for prioritized tickers.
- `BudgetGuard` has a documented path from shadow mode to report and enforce-ready behavior.

Quarterly target outcomes:

- A premium or GPT-5.5-class deep reviewer is used only for high-value routing cases, not for every ticker.
- Buy signal 5d and 20d hit rate and average return can be compared against the baseline.
- Decision confidence metadata incorporates evidence quality, data quality, and signal outcome feedback.
- Dashboard or PM-view consumption reduces the number of daily items the user must inspect while increasing evidence density per item.
- Monthly cost remains around USD 10 unless a run or mode explicitly warns that it may exceed that target.

## Non-Goals

- No real-time trading system.
- No trade execution or order automation.
- No direct external fetching outside the collector layer.
- No LLM or premium reviewer directly overwriting official decisions.
- No automatic factor weight changes before shadow evaluation, walk-forward validation, and explicit approval.
- No broad frontend redesign in the first implementation slice.
- No schema-breaking output changes unless a migration is explicitly documented.

## Current Baseline

The initial baseline should be recorded from existing run artifacts and logs.

Observed current baseline:

```text
watchlist_tickers: 23
latest_llm_calls: 179
latest_estimated_cost_usd: 0.4316217
latest_monthly_estimate_usd: 8.6 to 9.5 at 20 to 22 trading days
latest_validated_ticker_count: 283
latest_validation_failure_count: 17
latest_hallucination_warning_count: 35
latest_hallucination_ratio: 0.1237
search_evidence_provider: cache
search_evidence_searched_tickers: 0
search_evidence_coverage: 0
budget_guard_mode: shadow
budget_guard_would_block_count: 6
```

Known reliability issues in the current output set:

- `output/data/backtest_summary.json` failed JSON parsing due to an unterminated string.
- `output/data/search_audit.json` failed JSON parsing due to malformed text in claim fields.
- Several generated Korean strings appear mojibake-encoded in output/log views, which may indicate an encoding or serialization path that needs focused handling.

This baseline is not a judgment that the whole pipeline is broken. The primary pipeline can complete successfully. The problem is that performance improvement cannot be trusted unless output artifacts, audits, and baselines are themselves reliable.

## Accepted Approach

Use a measurement-first balanced plan.

This approach starts with artifact reliability and performance measurement, then layers in smarter model routing, evidence quality, signal learning, and PM-facing output. It avoids starting with a larger model rollout because the current measurement layer is not yet stable enough to prove whether expensive changes help.

Compared with a model-router-first plan, this is slower to produce visible premium-model changes but safer and more measurable. Compared with an evidence-only plan, it covers cost and signal performance instead of focusing only on hallucination and citation trust.

## Architecture Direction

The existing pipeline invariant remains unchanged:

```text
collect -> analyze -> state -> output -> store -> log
```

The masterplan adds four operating layers around existing responsibilities.

### 1. Measurement Core

Measurement Core reads output, log, eval, backtest, routing, and signal artifacts and produces stable performance summaries.

Responsibilities:

- verify generated JSON can be parsed
- compute run-level cost and call-count metrics
- compute quality warning rates
- compute evidence coverage and freshness metrics
- compute signal outcome and routing-value summaries when data exists
- emit machine-readable and human-readable reports

This layer is observational. It must not alter official decisions.

### 2. Smart Model Router

Smart Model Router limits deep review to the tickers where additional intelligence is most likely to matter.

Initial priority inputs:

- decision uncertainty or buy/watch boundary proximity
- portfolio exposure
- event proximity
- evidence gap
- recent volatility
- signal importance or action change
- economy versus deep disagreement

The router should make deep review explainable by recording why each ticker was selected or skipped.

### 3. Evidence Quality Layer

Evidence Quality Layer strengthens search evidence and claim audit reliability.

Collector remains the only layer that may call external providers. Downstream layers consume normalized evidence and aggregate evidence quality scores.

Decision integration begins as confidence metadata and shadow gates:

- strong evidence may increase confidence metadata
- weak evidence may flag or cap only in shadow/report mode at first
- provider failure should be distinguished from true lack of evidence
- missing search due to operational failure should not automatically punish a ticker

### 4. Signal Learning Loop

Signal Learning Loop connects later outcomes to decision factors without changing official weights immediately.

Initial flow:

```text
signal outcomes
-> factor attribution
-> suggested weight changes
-> shadow score
-> walk-forward validation
-> manual approval before enforce
```

This avoids overfitting and prevents early small-sample noise from changing production decision behavior.

## Layer Placement

### Collect

Collector owns external market, news, search, macro, policy, and provider calls.

Masterplan additions:

- improve search evidence cache and TTL behavior
- expose evidence coverage, source diversity, freshness, and provider status as normalized data
- keep provider failures separate from genuine zero-evidence results

### Analyze

Analyzer owns prompt construction, structured LLM calls, validation, and module diagnostics.

Masterplan additions:

- improve module-level validation retry telemetry
- attach cost and token telemetry to modules and routes
- keep evidence manifests hash-only and safe
- accept router-selected premium/deep review requests without turning router output into official decisions

### Decision

Decision remains the owner of official rule-based actions.

Masterplan additions:

- attach evidence quality, data quality, and signal history to confidence metadata
- keep official action generation rule-based
- support shadow/report/enforce-ready gates before any official action cap
- never let a premium reviewer directly create or overwrite a `buy`

### State

State owns reproducible signal outcomes and historical labels.

Masterplan additions:

- preserve 1d, 5d, 20d, and triple-barrier outcomes
- expose enough data for factor outcome attribution
- keep insufficient sample sizes explicit

### Output

Output owns deterministic Markdown and JSON artifacts.

Masterplan additions:

- protect all operational JSON through schema-safe serialization
- add baseline and trend performance artifacts
- write human-readable performance reports
- keep web-public mirrors as copies of `output/data`

### Store

Datastore remains the persistence boundary.

Masterplan additions:

- avoid bypassing datastore for historical prices or signal rows
- keep history queries stable for performance and learning reports

### Log

Logging remains observational and non-mutating.

Masterplan additions:

- summarize cost, call counts, retries, warning counts, evidence coverage, and routing decisions
- surface performance-report failures without failing the primary pipeline unless core artifacts are broken

## One-Month Execution Plan

### Week 1: Measurement Core Recovery

Fix the trustworthiness of generated artifacts.

Scope:

- ensure all generated operational JSON is parseable
- add regression coverage for `backtest_summary.json` and `search_audit.json`
- separate Markdown-oriented generated prose from JSON serialization paths
- make output health checks cover performance-critical artifacts
- create the first baseline KPI artifact

Expected outputs:

```text
output/data/performance_baseline.json
output/data/performance_trends.json
docs/reports/performance-YYYY-MM-DD.md
```

Success criteria:

- generated JSON parse failures are zero
- output health check covers the new performance artifacts
- baseline metrics can be loaded even when some inputs are missing

### Week 2: KPI Baseline And Comparison

Create a run-by-run comparison surface.

Initial KPIs:

- `cost_per_ticker`
- `llm_calls_per_ticker`
- `validation_retry_rate`
- `hallucination_ratio`
- `fact_warning_rate`
- `evidence_coverage`
- `evidence_freshness`
- `deep_selected_count`
- `deep_cost_share`
- `routing_conflict_count`
- `buy_hit_rate_5d`
- `buy_hit_rate_20d`
- `turnover`
- `json_parse_failure_count`

The aggregator must tolerate missing files and insufficient data. It should not invent performance claims when samples are too small.

### Week 3: Smart Model Router Version 1

Define and log a deterministic priority score for deep review.

Candidate formula:

```text
priority = uncertainty
         + portfolio_exposure
         + event_proximity
         + evidence_gap
         + volatility
         + signal_importance
```

Version 1 should focus on explainability and budget simulation.

Expected outputs:

- selected and skipped tickers with reason codes
- estimated incremental cost
- `skipped_due_to_budget` or `skipped_due_to_priority` reasons
- monthly USD 10 simulation
- report-mode BudgetGuard guidance

The first router pass may remain shadow/report-only if implementation risk is high.

### Week 4: Evidence Quality Version 1

Define the operating path from cache-only evidence to prioritized live search or refreshed evidence.

Scope:

- search only prioritized tickers, not the full watchlist every run
- keep provider calls inside collector-owned modules
- make claim audit output parseable and schema-stable
- attach evidence score to decision confidence metadata
- keep weak-evidence buy caps in shadow/report mode first

Target:

- move prioritized ticker evidence coverage from zero toward 50 percent or more
- distinguish no evidence, stale evidence, provider unavailable, and malformed cache
- document enforce conditions for future weak-evidence buy caps

## Quarterly Roadmap

### Phase 1: Premium Deep Reviewer

Use a premium or GPT-5.5-class reviewer only when the router indicates high value.

Candidate triggers:

- portfolio holding
- buy/watch boundary proximity
- high evidence gap plus high price or event importance
- high recent volatility
- major news or filing event
- disagreement between economy and existing deep or standard analysis

Premium reviewer output should first affect:

- consensus metadata
- PM summary
- risk and disagreement explanation
- future router-value measurement

It must not directly overwrite official actions.

### Phase 2: Signal Learning Loop

Start with shadow learning.

Inputs:

- signal tracker outcomes
- 1d, 5d, 20d returns
- triple-barrier labels
- decision factor scores
- market regime
- action and conviction

Outputs:

- factor outcome attribution
- sample-size-aware performance summaries
- suggested weight changes in shadow only
- walk-forward validation reports

No factor weight should change automatically before manual approval and adequate sample validation.

### Phase 3: Evidence-Confidence Integration

Connect evidence quality to decision confidence more deeply.

Initial behavior:

- strong evidence plus strong signal can strengthen confidence metadata
- strong signal plus weak evidence produces warning/report metadata
- repeated weak evidence or audit failures can become enforce candidates

Only late in the quarterly roadmap should weak-evidence buy caps move from shadow/report to enforce, and only with tests proving official behavior changes are intentional.

### Phase 4: PM View And Dashboard Consumption

Compress the daily review surface.

Preferred PM view sections:

- top opportunities
- avoid or downgrade candidates
- evidence-weak but high-momentum candidates
- portfolio risk changes
- model disagreement or committee objection highlights
- cost and quality status

The web app should consume output artifacts only. It must not recompute official decisions or call providers.

## Data Flow And Artifacts

The masterplan adds metadata flows beside the existing business data flow.

```text
collect
  -> normalized market/news/search evidence
  -> evidence coverage/freshness metadata

analyze
  -> ticker analysis
  -> module validation telemetry
  -> LLM call/token/cost/retry telemetry
  -> evidence manifest

decision
  -> official action
  -> conviction/confidence metadata
  -> evidence/data/signal quality annotations

state
  -> signal outcomes
  -> 1d/5d/20d returns
  -> triple-barrier labels
  -> factor outcome attribution inputs

output/log/eval
  -> performance baseline
  -> performance trends
  -> routing outcome
  -> quality report
  -> cost report
```

Primary artifacts:

```text
output/data/performance_baseline.json
output/data/performance_trends.json
docs/reports/performance-YYYY-MM-DD.md
output/data/routing_outcome.json
output/data/search_evidence.json
output/data/search_audit.json
output/data/signal_quality.json
```

Artifact rules:

- Every JSON artifact is written through standard JSON serialization.
- Markdown prose generation and JSON serialization paths are separated.
- Korean text, newlines, quotes, and special characters are valid JSON strings when emitted.
- `output_health_check` includes newly added performance artifacts.
- JSON parsing failure is a P0 issue for this masterplan.
- Schema changes should be additive by default.

## Error Handling And Safety

Error priority:

### P0: Unparseable Output Artifacts

Examples:

- broken JSON
- unterminated strings
- invalid escaping
- encoding corruption that breaks parsers

Handling:

- treat as blocking for performance work completion
- add regression tests
- verify through JSON loading and output health checks

### P1: Official Decision Quality Risk

Examples:

- weak evidence attached to strong buy recommendations
- hallucination warning spikes
- excessive validation retries

Handling:

- report first
- keep gates shadow-only until reviewed
- move to enforce only after explicit tests and approval

### P2: Cost Control Failure

Examples:

- `BudgetGuard` reports `would_block` while shadow mode keeps executing optional paths
- deep call count grows without measured routing value

Handling:

- report estimated overspend
- simulate enforce behavior
- enforce only optional deep paths first, never core analysis

### P3: Auxiliary Report Failure

Examples:

- Markdown performance report generation failure
- optional audit report failure

Handling:

- preserve primary pipeline success when safe
- record warnings in logs or API status
- keep machine-readable error metadata when possible

### BudgetGuard Progression

BudgetGuard should progress through:

```text
shadow -> report -> enforce-ready -> enforce
```

Definitions:

- `shadow`: record decisions only.
- `report`: surface would-block paths and estimated savings in performance reports.
- `enforce-ready`: tests and dry runs prove the expected optional-path skips.
- `enforce`: skip configured optional deep paths when caps are exceeded.

### Router Safety

- Official decisions remain rule-based.
- Premium reviewer output starts as consensus and PM metadata.
- A premium reviewer cannot directly create a `buy`.
- Evidence shortage starts as confidence warning/report metadata.

### Learning Loop Safety

- No automatic factor weight changes.
- Suggested weights are shadow-only.
- Walk-forward validation is required before any enforce path.
- Insufficient sample size must remain explicit.

## Testing And Verification

### Artifact Stability Tests

Required coverage:

- all generated `output/data/*.json` can be parsed
- `backtest_summary.json` malformed-string regression
- `search_audit.json` claim text regression
- Korean text, quotes, backslashes, and newlines serialize correctly
- output health check includes new performance artifacts

Success:

```text
generated_json_parse_failures == 0
output_health_check passes
```

### KPI Calculation Tests

Required coverage:

- load `cost_log`, `analysis_quality`, `routing_outcome`, and `signal_quality`
- tolerate missing files
- emit `insufficient_data` when samples are too small
- calculate cost per ticker, calls per ticker, warning rates, and evidence coverage
- avoid overstating performance when completed outcome samples are absent

### Router Tests

Required coverage:

- same input produces same priority and routing result
- uncertainty, portfolio exposure, event proximity, evidence gap, volatility, and signal importance affect priority
- budget cap simulation produces expected skip reasons
- selected and skipped reason codes are deterministic

### Evidence Quality Tests

Required coverage:

- cache-only mode with zero evidence remains valid
- mocked provider paths normalize evidence records
- provider failure differs from genuine no-evidence results
- evidence score attaches to confidence metadata without changing official actions in shadow mode
- weak-evidence buy cap remains shadow/report until enforce is explicitly configured

### Signal Learning Tests

Required coverage:

- 1d, 5d, and 20d outcome loading
- triple-barrier insufficient-data handling
- factor attribution sample-size guards
- suggested weights emitted only as shadow output
- no factor weight mutation before approval

Baseline verification commands:

```powershell
python -m unittest discover -s tests -v
python -m compileall main.py src tests
python -m src.cli.output_health_check
```

When frontend consumption changes:

```powershell
cd web
npm run build
```

## Decomposition Into Implementation Specs

This masterplan is intentionally larger than one implementation task. It should be decomposed into separate specs or plans.

### 1. Performance Measurement Core

Scope:

- JSON parse protection
- baseline and trend artifacts
- performance report
- output health check expansion
- cost, quality, evidence, and signal KPI definitions

### 2. Smart Model Router

Scope:

- priority calculation
- explainable selection and skip reasons
- BudgetGuard report and enforce-ready behavior
- USD 10 monthly simulation

### 3. Evidence Quality Layer

Scope:

- search evidence operating mode
- prioritized evidence refresh
- claim audit stability
- evidence score in confidence metadata

### 4. Signal Learning Loop

Scope:

- factor outcome attribution
- shadow weight suggestion
- walk-forward validation
- manual approval before factor weight enforcement

### 5. PM View And Dashboard Consumption

Scope:

- compact PM-facing summaries
- top opportunities and downgrade candidates
- evidence and quality status presentation
- no web-side recomputation of official decisions

## Acceptance Criteria

- The pipeline invariant remains `collect -> analyze -> state -> output -> store -> log`.
- Monthly cost target around USD 10 is documented and surfaced in performance reports.
- JSON parsing failure is treated as P0 and covered by tests.
- Run-by-run performance KPIs are machine-readable.
- Deep review and premium reviewer use are priority-based and explainable.
- Evidence, data, and signal quality first affect confidence metadata and reports.
- Official decisions are not directly overwritten by LLM reviewers.
- Factor weight changes remain shadow-only until validated and explicitly approved.
- Schema changes are additive unless a migration is documented.
- Relevant layer docs are updated as implementation specs touch behavior.

## Open Risks

### Measurement Before Improvement

Risk: The first implementation slice may feel like maintenance rather than performance improvement.

Mitigation: Make the baseline and trend report immediately useful by showing cost, quality, evidence, and signal metrics together.

### Premium Model Cost Drift

Risk: GPT-5.5-class review could push monthly cost above USD 10.

Mitigation: require router selection, BudgetGuard simulation, and report-mode cost forecasts before enabling premium review.

### Small Sample Overinterpretation

Risk: early signal outcome metrics may look authoritative with too few completed signals.

Mitigation: emit `insufficient_data`, sample counts, and confidence labels; keep learning shadow-only.

### Evidence Provider Failure

Risk: live search outages could be misread as weak evidence.

Mitigation: distinguish provider unavailable, stale cache, no evidence found, and malformed cache states.

### Layer Boundary Drift

Risk: model routing, evidence quality, and dashboard summaries could pull logic into the wrong layer.

Mitigation: keep external fetching in collector, official decisions in decision, formatting in output/web, and persistence behind datastore.

