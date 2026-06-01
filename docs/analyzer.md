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
* Eligibility is driven by the configured conviction trigger range; `portfolio_priority` can force current holdings into the deep-pass candidate set
* Smart Model Router V1 ranks eligible deep-review candidates by deterministic priority score before applying `max_daily_ensemble`
* Router priority scores are based on boundary proximity, portfolio exposure, upcoming events, evidence gap, volatility, and directional signal importance
* Router-selected tickers are exposed through diagnostics as `selected_tickers`; the pipeline passes them to the collector as search evidence refresh priorities without increasing model or provider caps
* Conflicts may trigger a third review
* BudgetGuard records shadow decisions before deep and tie-break routes
* Routing logs record each ticker's selection reason, portfolio flag, action, conviction, router priority score, router reason codes, priority skips, and estimated deep-review cost
* Final analysis payload remains schema-compatible with the rest of the pipeline

### Committee Flow

* After ensemble analysis, every ticker receives a role-based committee pass
* Roles are `growth_analyst`, `value_skeptic`, `risk_manager`, `macro_strategist`, and `pm`
* Round 1 uses the configured committee economy profile for all roles
* Low PM confidence or strong Risk/Macro objections trigger selective deep reruns for `risk_manager`, `macro_strategist`, and `pm`
* BudgetGuard records a shadow decision before selective deep committee reruns
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

Prompt templates reinforce these guards before validation: `key_news` must not rewrite English source headlines into new English titles, and narrative/risk modules must use numeric values and measurable triggers directly from the input payload instead of calculating or rounding new values.

For `signal_or_takeaway`, validation follows dedicated signal rules rather than
the generic numeric mismatch scanner. Target and stop values that match
`must_use_values` are allowed even when they are far from current price, and
`N/A/N/A` targets are accepted when the prompt explicitly asks the model not to
guess missing levels. Fallback signals must use the same structured
`진입 트리거 ... | 목표 A/B | 손절 ...` shape.

## Model Profiles And Runtime

* Per-module model profile and batch-size selection in `src/utils/model_config.py`
* `budget_guard` config in `config/models.yaml` controls shadow/enforce behavior for guarded optional LLM paths
* `ensemble.emit_routing_log` should remain enabled for router observability; it writes routing metadata only and does not add model calls
* `llm_runtime.py` enforces a missing-ticker retry budget so partial batches are recovered without runaway cost

## LLM Evidence Manifest

Before provider calls, analyzer LLM paths emit best-effort evidence manifest records under `output/data/llm_evidence/<run_date>.jsonl`. Records contain hashes and metadata only; they must not contain raw prompts, full payloads, model responses, API keys, or sensitive environment values.

Ticker-level structured modules record `raw_payload_hash`, `fallback_payload_hash`, `upstream_payload_hash`, `macro_context_hash`, `market_regime_hash`, and `prompt_template_hash` per ticker. Economy, deep, and tie-break runs may differ by model profile or prompt version, but comparable ticker records for the same run should share raw, macro, and regime hashes.

Committee, macro narrative, policy impact, and weekly insight paths record scope-specific evidence hashes. Manifest writes are best-effort and must not fail the daily pipeline.

## Search Audit

`src/analyzer/search_audit.py` performs a deterministic, observational comparison between existing `TickerAnalysis` claim text and normalized `search_evidence.json` items. It does not call providers, prompt the LLM, write files, or change official decisions.

The audit extracts compact claims from summary, signal, financial highlight, risk, and key-news fields, then labels each claim as `supported`, `conflicting`, `missing_evidence`, or `insufficient_evidence` based on token and numeric overlap with same-ticker search evidence. Before matching, it splits multi-sentence and pipe-delimited text into smaller claims, excludes internal market-data-only statements such as price, SMA, RSI, 52-week position, RVOL, ATR, options-level checks, PER/ROE/FCF, forward or TTM EPS metrics, analyst targets, and next-earnings date metrics, and only audits claims that contain explicit external-evidence terms. Those internal observations are validated by collector/analyzer data paths, while search audit focuses on external evidence such as revenue, guidance, filings, contracts, demand, supply, dividends, litigation, regulatory claims, earnings beats, reported results, and upgrades or downgrades. ASCII evidence terms are matched as whole tokens so `Sector` is not treated as `SEC`, and SEC form labels such as `10-Q` or `8-K` are ignored during numeric conflict checks. The output layer writes the resulting payload to `output/data/search_audit.json`.

## Rules

* No direct external API calls
* No presentation formatting
* No storage writes except through explicit output/state flows outside analyzer
* Output must remain deterministic enough for regression testing
* Fallbacks must preserve downstream payload shape
* Committee output must not replace the rule-based decision layer as the official action source
