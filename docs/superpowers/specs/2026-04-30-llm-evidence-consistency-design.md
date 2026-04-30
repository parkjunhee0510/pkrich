# LLM Evidence Consistency Design

## Purpose

The pipeline should be able to prove that its LLM reasoning steps used a consistent evidence base during a daily run. The current analyzer already routes normalized collected data through `AnalysisContext`, structured prompt templates, ensemble re-analysis, and committee review. The missing piece is an auditable record of the exact input snapshots each LLM call saw.

This design adds a lightweight evidence manifest and an audit check. It does not change model prompts, decisions, or output payloads. It records compact hashes and metadata immediately before LLM calls, then uses those records to detect inconsistent evidence across economy, deep, tie-break, committee, macro narrative, policy impact, and weekly insight flows.

## Current Observations

The main daily path builds `collected`, `news_map`, `macro_context`, `market_regime`, `signal_history_map`, and `peer_candidates_by_ticker` once in `run_pipeline()`, then passes them into `AnalysisEnsemble`. Economy, deep, and tie-break analysis all reuse the same run date and macro context, while deep and tie-break start from economy-derived intermediate payloads.

Structured ticker LLM modules run through `run_structured_llm_module()`. Runtime prompt construction uses `PromptTemplate` from `src/analyzer/prompts/`, not the module-local `build_system_prompt()` and `build_user_prompt()` methods. Any evidence manifest must therefore capture both module payload hashes and prompt template identity.

Committee review is a separate LLM path. It receives final `TickerAnalysis` objects, then slims each analysis differently by role. Role payload hashes are expected to differ, but all committee roles for one ticker should share the same final analysis lineage.

Macro narrative is a run-level LLM path with optional web search and a 24-hour cache. It should be linked to the same run-level macro context and market regime used by ticker-level analysis.

The repository already has `src/eval` audit infrastructure with checks for schema stability, numeric grounding, citation integrity, contradiction, semantic drift, committee agreement, and retry distribution. The new consistency check should extend this framework instead of creating a separate reporting system.

## Goals

- Record the evidence identity used by each LLM call without storing full prompts, full payloads, API responses, or sensitive environment values.
- Detect when economy, deep, or tie-break analysis for the same ticker used different raw, macro, or regime evidence in the same run.
- Detect when committee roles for the same ticker were not grounded in the same final analysis lineage.
- Link run-level macro narrative records to ticker-level macro evidence.
- Keep the pipeline behavior unchanged if evidence recording fails.
- Fit into the existing audit output model under `src/eval`.

## Non-Goals

- Do not change trading decisions, prompt wording, model selection, or LLM response parsing.
- Do not store raw prompt text, full model response text, API keys, or large ticker payloads.
- Do not make evidence recording a hard dependency for the daily pipeline.
- Do not replace the existing analyzer context with a central evidence snapshot in this phase.
- Do not add a web UI for evidence review in this phase.

## Chosen Approach

Use an LLM Evidence Manifest plus an Eval Check.

Each LLM call site emits small JSONL records before calling the provider. Records contain stable hashes of the inputs and metadata about module, scope, model profile, prompt version, and lineage. The eval layer reads these records and reports pass, warn, fail, or info based on consistency rules.

This approach is intentionally narrower than a full central evidence snapshot refactor. It creates operational proof first, while keeping a later refactor possible if the audit shows recurring inconsistency.

## Manifest Location

Evidence records should be written to:

```text
output/data/llm_evidence/<run_date>.jsonl
```

The file is an operational artifact for audit tooling. It is not a user-facing dashboard payload and should not be copied into web public data by default.

## Canonical Hashing

Hashes should use a shared helper so all call sites use identical rules.

Canonical JSON should use sorted keys, compact separators, deterministic fallback stringification for dates and datetimes, and ASCII-safe serialization. The hash format should be:

```text
sha256:<hex>
```

Missing values should not silently hash as an empty object. Each record should include presence flags such as `macro_context_present`, `market_regime_present`, or `upstream_payload_present` so the audit can distinguish "same evidence" from "same missing evidence".

## Structured LLM Module Records

For ticker-level structured modules, emit one record per ticker per module call. Batch-level metadata is repeated on each ticker record because consistency checks are ticker-centered.

Example shape:

```json
{
  "schema_version": 1,
  "run_date": "2026-04-30",
  "stage": "analyzer",
  "scope": "ticker",
  "module": "research_narrative_module",
  "ticker": "NVDA",
  "batch_tickers": ["NVDA", "MSFT", "AAPL"],
  "execution_mode": "full",
  "model": "gpt-5.4-mini",
  "model_profile": "economy",
  "prompt_version": "research_v1",
  "raw_payload_hash": "sha256:...",
  "fallback_payload_hash": "sha256:...",
  "upstream_payload_hash": "sha256:...",
  "macro_context_hash": "sha256:...",
  "market_regime_hash": "sha256:...",
  "prompt_template_hash": "sha256:...",
  "macro_context_present": true,
  "market_regime_present": true,
  "upstream_payload_present": true,
  "created_at": "2026-04-30T00:12:00Z"
}
```

Economy, deep, and tie-break may differ in `model`, `model_profile`, `prompt_version`, and `prompt_template_hash` by design. They should not differ in `raw_payload_hash`, `macro_context_hash`, or `market_regime_hash` for the same `run_date + ticker`.

## Macro Narrative Records

Macro narrative should emit one run-scope record for each attempted run-level narrative decision. The record should identify the macro prompt payload, market regime, cache behavior, and source.

Example fields:

```text
scope = "run"
stage = "analyzer"
module = "macro_narrative"
macro_prompt_payload_hash
macro_context_hash
market_regime_hash
cache_status = "hit" | "miss" | "refresh" | "fallback"
source = "llm" | "fallback"
model
```

Ticker-level records can then be checked against the same run-level `macro_context_hash` and `market_regime_hash`.

## Committee Records

Committee records should be emitted once per role call. Because role payloads are intentionally slimmed differently, `role_payload_hash` is role-specific and should not be compared across roles. Instead, all roles for the same ticker should share the same `analysis_payload_hash` and the same lineage metadata.

Example fields:

```text
scope = "committee_role"
stage = "committee"
module = "committee_<role>"
ticker
role
round = "economy" | "deep"
model
model_profile
analysis_payload_hash
role_payload_hash
prior_role_outputs_hash
prompt_template_hash
macro_context_hash
market_regime_hash
```

The current committee prompt is based on the final `TickerAnalysis`, not the original `AnalysisContext`. If macro or regime evidence is not directly available to the committee hook, the record should explicitly mark it missing instead of manufacturing a value. The audit should treat missing committee macro/regime linkage as warn in the first implementation, because existing committee behavior may not expose those fields yet.

## Policy Impact And Weekly Insight Records

Policy impact and weekly insight are also LLM reasoning paths, but their inputs are not the same ticker-analysis evidence bundle.

Policy impact should record chunk-level and event-level hashes:

```text
scope = "policy_chunk"
stage = "policy"
module = "policy_impact"
events_hash
candidate_tickers_hash
category_to_sectors_hash
model_profile
```

Weekly insight should record one run-level hash:

```text
scope = "weekly"
stage = "analyzer"
module = "weekly_insight_module"
weekly_inputs_hash
macro_context_hash
market_regime_hash
model_profile
prompt_version
```

The first consistency check should include these records in inventory and missingness reporting. Strict cross-module equality rules should focus on the daily ticker analysis and committee lineage, where comparable evidence exists.

## Consistency Rules

The new eval check should report:

- `pass` when comparable records for the same run and ticker share the expected evidence hashes.
- `warn` when non-critical linkage is missing, such as committee macro/regime metadata or a macro narrative record that cannot be joined to a ticker record.
- `fail` when comparable economy, deep, or tie-break records for the same ticker have different raw payload, macro context, or market regime hashes.
- `fail` when deep or tie-break analysis starts from a lineage that cannot be traced back to the economy analysis for the same ticker.
- `info` when a run has no manifest records because it predates this feature or evidence recording was disabled.

The check should not fail because prompt versions differ between economy and deep profiles. That difference is intentional and configured in `config/models.yaml`.

## Error Handling

Evidence recording is best-effort. A manifest write failure should never fail the pipeline or suppress LLM analysis. The writer should catch exceptions and emit a pipeline warning such as `llm_evidence_write_failed`.

Because structured LLM batches can run in parallel worker threads, JSONL append operations should go through one helper with a process-local lock. This keeps records line-oriented and avoids interleaved writes.

If hashing fails for one field, the record should still be emitted with a field-specific status that explains the failure. The audit can then warn or fail based on the missing field's importance.

## Testing Strategy

Hash tests should verify that key order does not change the hash, dates and datetimes serialize deterministically, and missing values remain distinguishable from empty objects.

Writer tests should verify that one JSONL record is written with the expected schema, that write failures are swallowed with a warning, and that no raw prompt or response fields are persisted.

Runtime hook tests should mock provider calls and verify evidence emission from `run_structured_llm_module()`, `macro_narrative.py`, `committee.py`, `policy_impact.py`, and `WeeklyInsightModule` without making real OpenAI requests.

Eval check tests should cover pass, warn, fail, and info outcomes using small fixture manifests. A mismatch in `macro_context_hash` between economy and deep records should fail. Missing legacy manifests should report info. Missing committee macro/regime linkage should warn in the first implementation.

## Documentation Updates For Implementation

Implementation should update `docs/analyzer.md` with the evidence manifest contract and `docs/output.md` with the new operational artifact path. If the eval report shape changes, `src/eval/README.md` should list the new check and explain its verdict semantics.

## Rollout

The first rollout should add the manifest writer, hook the core daily LLM paths, and add the eval check in read-only mode. The daily pipeline should continue even when records are incomplete.

After at least one successful run, the report can be reviewed to decide whether committee should receive explicit macro/regime lineage fields in a later implementation. That would be a behavior-preserving prompt-context improvement, not part of this initial proof layer.
