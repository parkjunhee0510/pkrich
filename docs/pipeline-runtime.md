# Pipeline Runtime

## Codex Routing

- Read when the task changes execution order, stage responsibilities, feature flags, entrypoints, or pipeline-side output phases.
- Pair with `docs/pipeline-boundaries.md` only if the change also alters cross-layer contracts.
- Then inspect `src/pipeline.py` and the specific stage modules involved.

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
* Load normalized search evidence from cache for post-decision shadow quality metadata and audit artifacts
* Collect market overview and macro context
* Collect macro v2 inputs: economic surprise (`macro_surprise.py`) and scheduled macro events (`macro_events.py`)
* Detect actual market date from collected price history
* Backfill missing prices from datastore history when the collector returns gaps
* Load peer candidate sets for later analyzer modules

### 3. Analyze

Owned by `analyzer/`.

Current responsibilities:
* Build raw and fallback payloads per ticker
* Resolve module order with `ModuleRegistry`
* Run non-LLM modules first, then LLM modules
* Produce ticker-level analysis payloads plus portfolio-level results such as `portfolio_risk`
* Produce macro narrative and per-ticker macro sensitivity
* Run multi-model consensus through `AnalysisEnsemble`
* Record BudgetGuard shadow decisions before guarded optional deep LLM paths
* Apply validator hallucination guards through `validator.py` and `signal_levels.py`

Current analyzer stack:
* `AnalysisOrchestrator`
* `AnalysisEnsemble`
* modules under `src/analyzer/modules/`
* prompt registry under `src/analyzer/prompts/`

Current ensemble flow:
* Economy profile analyzes the full watchlist first
* Only selected tickers receive deep LLM-only re-analysis
* Selection is based on the ensemble trigger range, with optional portfolio-priority routing for current holdings
* If economy and deep disagree, an optional third review can run
* Optional routing logs persist per-ticker selection reasons for later routing outcome analysis
* Final analysis source is `third_review > deep > economy`
* BudgetGuard is shadow-only by default and does not skip these routes unless explicitly switched to enforce mode

### 3b. Decision

Owned by `decision/`.

Responsibilities:
* Consume the run-level market regime detected earlier in the run
* Generate factor scores, conviction, confidence metadata, and official `buy` / `watch` / `avoid`
* Attach search evidence score and `search_quality_gate` metadata in shadow mode after official actions are generated
* Keep official actions rule-based even when upstream analysis used LLMs

### 4. State

Owned by `state/` and datastore-backed utilities.

Current responsibilities:
* Run a pre-decision state refresh that updates realized returns for prior signals from stored price history
* Apply triple-barrier signal labeling before decision generation
* Load `signal_stats` for decision inputs
* Record new daily signals from analyses and decisions
* Reload signal statistics for output and future runs

### 5. Output

Owned by `output/`.

Current responsibilities:
* Write daily, weekly, and per-ticker Markdown
* Write sharded JSON payloads for web consumption
* Write portfolio, weekly summary, routing, quality, and cost artifacts
* Emit auxiliary outputs such as sector explorer payloads and intraday refresh payloads
* Write API status for the calendar run date, even when market data resolves to an earlier effective market date
* Treat `output/data` as the source of truth and sync selected web-facing payloads into `web/public/output/data/` when the static web app is present

Important output families:
* `output/data/index.json`
* `output/data/tickers/<TICKER>/latest.json`
* `output/data/tickers/<TICKER>/history.json`
* `output/data/api_status.json`
* `output/data/analysis_quality.json`
* `output/data/cost_log.json`
* `output/data/routing_outcome.json`
* `output/data/search_evidence.json`
* `output/data/search_audit.json`
* `docs/reports/llm-audit-YYYY-MM-DD.md`
* `output/data/llm_audit/YYYY-MM-DD.json`

### 6. Store

Owned by `utils/datastore.py` and backend implementations.

Current responsibilities:
* Persist price history and analysis-run metadata
* Query signal statistics and historical prices
* Provide one storage boundary for CSV and SQLite backends

### 7. Log

Owned by pipeline logging helpers.

Current responsibilities:
* Record step-level pipeline events
* Finalize per-run logs
* Derive operational outputs such as API status, quality, and cost reports

## Feature Flags And Routing

## Default Versus Full Runs

`python main.py` runs the primary watchlist pipeline and finishes after watchlist outputs, web-facing JSON mirrors, alerts, and pipeline logs are complete. It does not refresh the sector explorer payload by default.

`python main.py --with-sectors` runs the same primary watchlist pipeline and then refreshes the sector explorer payload through the existing sector scan path.

`python main.py --collect-only` remains the intraday refresh path and does not run sector scanning, even when `--with-sectors` is also passed.

Default runs emit `sector_scan_skipped` with the reason `disabled_by_default`. Full runs emit `sector_scan_completed` when the sector scan succeeds.

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
