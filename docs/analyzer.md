# Analyzer

## Codex Routing

- Read when the task changes `src/analyzer/`, prompts, batching, or structured LLM output.
- Pair with `docs/cost.md` for model, token, or batching decisions.
- Then inspect `src/analyzer/` and `config/models.yaml`.

## Purpose

Transform normalized collected data into structured research outputs.

## Current Architecture

The analyzer is module-based.

Core pieces:
* `AnalysisModule` contracts in `src/analyzer/base.py`
* `ModuleRegistry` for dependency ordering
* `AnalysisOrchestrator` for DAG execution
* `AnalysisEnsemble` for economy/deep/third-review consensus
* `PromptTemplate` prompt sets in `src/analyzer/prompts/`

## Execution Model

### Module Ordering

* Modules declare `requires` and `produces`
* `ModuleRegistry.resolve_order()` computes a DAG
* Non-LLM modules run before LLM modules in normal execution
* `llm_only` execution is supported for ensemble re-analysis

### Payload Flow

* Raw payloads are built from collected inputs
* Fallback payloads guarantee schema-safe defaults
* Intermediate module results merge by ticker
* Portfolio-level module results are accumulated separately

### LLM Flow

* Prompt version is selected from model profile config
* LLM modules run in module-specific batches
* Structured schema validation is required
* Deterministic fallback is required per module on failure

### Ensemble Flow

* Economy profile analyzes the full watchlist first
* Selected tickers receive deeper LLM-only re-analysis
* Conflicts may trigger a third review
* Final analysis payload remains schema-compatible with the rest of the pipeline

### Committee Flow

* After ensemble analysis, every ticker receives a role-based committee pass
* Roles are `growth_analyst`, `value_skeptic`, `risk_manager`, `macro_strategist`, and `pm`
* Round 1 uses the configured committee economy profile for all roles
* Low PM confidence or strong Risk/Macro objections trigger selective deep reruns for `risk_manager`, `macro_strategist`, and `pm`
* Committee output is stored on `TickerAnalysis.committee_analysis` for downstream output only
* Committee role calls use a per-role strict JSON schema on the Responses API
* Parser fallback also accepts common alias fields such as `recommendation`/`rationale`/`confidence_score` and fenced JSON text when the model output shape drifts
* Validation marks each role with `valid` and `invalid_reason` instead of silently dropping malformed outputs
* Committee JSON keys remain English, but role `summary` values must be Korean; only ticker names, metrics, and source names may remain as-is

## Current Module Families

Deterministic modules:
* peer comparison
* valuation
* trade frame
* portfolio risk

Structured LLM modules:
* news analysis
* research narrative
* risk assessment
* signal takeaway
* macro narrative (`macro_narrative.py`)
* weekly insight generation on weekly summary paths

## Validator Guards

`validator.py` enforces hallucination guards on LLM output:
* Price logic checks (supports/resistances vs current price)
* Fact warnings for unverifiable claims
* Pattern enforcement via `signal_levels.py`

## Model Profiles And Runtime

* Per-module model profile and batch-size selection in `src/utils/model_config.py`
* `llm_runtime.py` enforces a missing-ticker retry budget so partial batches are recovered without runaway cost

## LLM Evidence Manifest

Before provider calls, analyzer LLM paths emit best-effort evidence manifest records under `output/data/llm_evidence/<run_date>.jsonl`. Records contain hashes and metadata only; they must not contain raw prompts, full payloads, model responses, API keys, or sensitive environment values.

Ticker-level structured modules record `raw_payload_hash`, `fallback_payload_hash`, `upstream_payload_hash`, `macro_context_hash`, `market_regime_hash`, and `prompt_template_hash` per ticker. Economy, deep, and tie-break runs may differ by model profile or prompt version, but comparable ticker records for the same run should share raw, macro, and regime hashes.

Committee, macro narrative, policy impact, and weekly insight paths record scope-specific evidence hashes. Manifest writes are best-effort and must not fail the daily pipeline.

## Rules

* No direct external API calls
* No presentation formatting
* No storage writes except through explicit output/state flows outside analyzer
* Output must remain deterministic enough for regression testing
* Fallbacks must preserve downstream payload shape
* Committee output must not replace the rule-based decision layer as the official action source
