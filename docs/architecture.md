# Architecture

## Principles

* Batch-first design
* Strict separation of concerns
* Deterministic outputs
* Cost-aware execution
* One storage boundary through datastore

## Layers

### `collector/`

Responsibilities:
* External data fetching only
* Provider fallback chains
* Data normalization before handoff

Must not:
* Perform LLM analysis
* Format user-facing output
* Write storage directly outside datastore utilities

### `analyzer/`

Responsibilities:
* Structured analysis from collected inputs
* Module DAG orchestration
* Prompt rendering, validation, and deterministic fallback
* Multi-model consensus for selected tickers

Key components:
* `ModuleRegistry`
* `AnalysisOrchestrator`
* `AnalysisEnsemble`
* `PromptTemplate` registry
* Modules under `src/analyzer/modules/`

Must not:
* Call external market/news APIs directly
* Own output formatting
* Bypass model-profile or prompt-version configuration

### `decision/`

Responsibilities:
* Plugin-based factor scoring
* Regime-aware weighting and normalization
* Final `buy/watch/avoid` decision generation

Key components:
* `DecisionFactor`
* factor registry under `src/decision/factors/` (includes `macro_regime_factor`, `macro_event_factor`)
* `MarketRegime` with sub-regime classification in `src/decision/market_regime.py`
* `ConvictionScorer`
* `generate_decisions(...)` in `src/decision/decision_layer.py` (surfaces `factor_reasoning`)

Must not:
* Fetch external data
* Write output files

### `state/`

Responsibilities:
* Signal history tracking
* Return windows and derived signal outcomes
* Reproducible state updates across runs

Must not:
* Depend on live APIs
* Hide non-reproducible side effects

### `output/`

Responsibilities:
* Markdown generation
* JSON export for web and analytics views
* Operational artifacts such as quality, routing, and cost logs

Must not:
* Fetch data
* Recompute business logic that belongs in analyzer or decision

### `datastore/`

Responsibilities:
* Unified persistence boundary
* CSV and SQLite backends
* Historical query surface for prices, signals, and run metadata

Must not:
* Leak backend-specific logic into other layers

### `logging/`

Responsibilities:
* Step-level pipeline event tracking
* Run summaries and operational diagnostics

Must not:
* Change pipeline outcomes
* Expose secrets

### `utils/`

Responsibilities:
* Shared helpers that do not own domain workflows
* Macro sensitivity computation (`macro_sensitivity.py`) applied to all collected tickers
* Ticker macro beta estimation (`ticker_macro_beta.py`)
* Macro event matching helpers (`macro_event_match.py`) used by macro v2 factors
* Module-specific model profiles and batch sizes (`model_config.py`)

Must not:
* Become a hidden domain layer

## Current End-To-End Shape

The current production path is:
* `collector` gathers normalized data
* `analyzer` builds analyses through module orchestration and ensemble review
* `decision` converts analyses into conviction-based actions
* `state` updates signal history and derived outcomes
* `output` writes Markdown and JSON payloads
* `datastore` persists run metadata and historical records
* `logging` records execution and derives operational reports

## Boundary Rules

* Never bypass datastore for persistence
* Never move business rules into GitHub Actions or Vercel build scripts
* Never let output formatting become the source of truth for analysis logic
* Never let analyzer perform direct provider fetching
* Keep optional features additive and non-destructive
