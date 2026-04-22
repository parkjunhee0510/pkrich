# Analyzer

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
* weekly insight generation on weekly summary paths

## Rules

* No direct external API calls
* No presentation formatting
* No storage writes except through explicit output/state flows outside analyzer
* Output must remain deterministic enough for regression testing
* Fallbacks must preserve downstream payload shape
