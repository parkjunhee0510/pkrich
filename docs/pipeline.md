# Pipeline

## Overview

The system runs as a deterministic batch pipeline.

Core invariant:
collect -> analyze -> state -> output -> store -> log

Primary entrypoint:
* `src/pipeline.py::run_pipeline()`

Secondary entrypoint:
* `src/pipeline.py::collect_only()` for intraday price refresh without full analysis

## Runtime Flow

### 1. Load Configuration

* Load environment variables
* Load watchlist and portfolio inputs
* Initialize datastore and pipeline logger

### 2. Collect

Owned by `collector/`.

Current responsibilities:
* Collect ticker market data through the market-data orchestrator
* Collect daily news through the news path selected by feature flags
* Collect market overview and macro context
* Collect macro v2 inputs: economic surprise (`macro_surprise.py`) and scheduled macro events (`macro_events.py`)
* Detect actual market date from collected price history
* Backfill missing prices from datastore history when the collector returns gaps
* Load peer candidate sets for later analyzer modules (yfinance primary via `yfinance_peer_metrics.py`, FMP fallback)

Rules:
* External APIs are allowed only here
* Fallback chains live here
* Outputs must be normalized before leaving this step

### 3. Analyze

Owned by `analyzer/`.

Current responsibilities:
* Build raw and fallback payloads per ticker
* Resolve module order with `ModuleRegistry`
* Run non-LLM modules first, then LLM modules
* Produce ticker-level analysis payloads plus portfolio-level results such as `portfolio_risk`
* Produce macro narrative via `macro_narrative.py` and per-ticker macro sensitivity (all collected tickers, not just portfolio)
* Run multi-model consensus through `AnalysisEnsemble`
* Apply validator hallucination guards (price logic checks, fact warnings, pattern enforcement) via `validator.py` and `signal_levels.py`

Current analyzer stack:
* `AnalysisOrchestrator`
* `AnalysisEnsemble`
* Modules under `src/analyzer/modules/`
* PromptTemplate registry under `src/analyzer/prompts/`

Current ensemble flow:
* Economy profile analyzes the full watchlist first
* Only selected tickers receive deep LLM-only re-analysis
* If economy and deep disagree, an optional third review can run
* Final analysis source is `third_review > deep > economy`

Rules:
* No direct external data fetching
* LLM outputs must remain structured and deterministic
* Fallbacks must preserve downstream schema stability

### 3b. Decide

Owned by `decision/`.

Current responsibilities:
* Classify market regime and sub-regime (`market_regime.py`)
* Run registered factors including `macro_regime_factor` and `macro_event_factor`
* Score conviction and generate buy/watch/avoid actions
* Surface `factor_reasoning` for downstream output consumption

Rules:
* No external data fetching
* No output formatting

### 4. State

Owned by `state/` and datastore-backed utilities.

Current responsibilities:
* Update tracked signal returns
* Apply triple-barrier signal labeling
* Record new daily signals from analyses and decisions
* Recompute signal statistics used by the decision layer and outputs

Rules:
* State must be reproducible from stored inputs and prior outputs
* No external API dependency

### 5. Output

Owned by `output/`.

Current responsibilities:
* Write daily, weekly, and per-ticker Markdown
* Write sharded JSON payloads for web consumption
* Write portfolio, weekly summary, routing, quality, and cost artifacts
* Emit auxiliary outputs such as sector explorer payloads and intraday refresh payloads

Important output families:
* `output/data/index.json`
* `output/data/tickers/<TICKER>/latest.json`
* `output/data/tickers/<TICKER>/history.json`
* `output/data/api_status.json`
* `output/data/analysis_quality.json`
* `output/data/cost_log.json`
* `output/data/routing_outcome.json`

Rules:
* No data fetching
* No new analysis logic
* Keep payloads deterministic and diff-friendly

### 6. Store

Owned by `utils/datastore.py` and backend implementations.

Current responsibilities:
* Persist price history and analysis-run metadata
* Query signal statistics and historical prices
* Provide one storage boundary for CSV and SQLite backends

Rules:
* All persistence must go through the datastore abstraction
* No direct backend access from analyzer, output, or decision code

### 7. Log

Owned by pipeline logging helpers.

Current responsibilities:
* Record step-level pipeline events
* Finalize per-run logs
* Derive operational outputs such as API status, quality, and cost reports

Rules:
* Logging must not change business behavior
* Logging failures should not take down the pipeline unless the primary run has already failed

## Feature Flags And Routing

The pipeline still contains controlled migration paths.

Examples:
* `ENABLE_ORCHESTRATOR_PRIMARY`
* `ENABLE_ORCHESTRATOR_SHADOW`
* `ENABLE_NEWS_ORCHESTRATOR_PRIMARY`
* `ENABLE_NEWS_ORCHESTRATOR_SHADOW`

Policy:
* Shadow mode may compare implementations
* Primary mode decides the source of truth
* Feature flags must not bypass layer boundaries

## Completion Criteria

A healthy run should:
* Complete end-to-end without breaking the invariant order
* Produce valid ticker analyses and decisions
* Update state and derived metrics
* Write deterministic Markdown and JSON outputs
* Record pipeline logs and operational summaries
