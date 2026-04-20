# Pipeline

## Overview

The system operates as a deterministic daily batch pipeline.

Core invariant:
collect → analyze → state → output → store → log

## Steps

### 1. Scheduler

* Triggered via GitHub Actions
* Orchestrates execution only (no business logic)

### 2. Load Configuration

* Load watchlist.yaml and portfolio.yaml
* Validate configuration before execution

### 3. Data Collection (collector/)

* Fetch market, financial, news, and filing data
* Apply fallback chain per source
* Output must be normalized

### 4. Analysis (analyzer/)

* LLM-based structured analysis
* Deterministic prompts and schema
* Supports batching and fallback

### 5. State Update (state/)

* Portfolio valuation (P&L)
* Signal tracking and performance updates
* Derived metrics computation

### 6. Output Generation (output/)

* Generate Markdown (daily, weekly, ticker)
* Generate JSON (dashboard, timelines, price history)

### 7. Storage (datastore/)

* Persist structured data
* Backend selectable (CSV / SQLite)
* Must remain transparent to other layers

### 8. Logging (logging/)

* Record pipeline events (JSONL)
* Generate summary report

## Invariants

* Pipeline order must not change
* Each step must be independently testable
* Non-critical failures must not break pipeline
