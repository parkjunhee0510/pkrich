# Architecture

## Principles

* Batch-first design
* Strict separation of concerns
* Deterministic outputs
* Cost-aware execution

## Layers

### collector/

* External data fetching only
* Implements fallback chains
* No analysis or formatting logic

### analyzer/

* LLM-based processing only
* Deterministic structured output
* No direct API calls outside LLM

### state/

* Portfolio tracking
* Signal tracking
* Derived metrics (returns, performance)

### output/

* Markdown and JSON generation
* No data fetching or analysis

### datastore/

* Storage abstraction layer
* Supports CSV and SQLite backends
* Selected via environment variable

### logging/

* Pipeline event tracking
* JSONL event stream + summary reports

### utils/

* Shared utilities only
* No domain logic

## Rules

* Never mix responsibilities across layers
* Never bypass datastore abstraction
* Never embed logic into GitHub Actions
