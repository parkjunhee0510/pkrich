# AGENTS.md

## Overview

This repository implements a **low-cost, batch-based stock research automation system**.

The system:

* runs daily via GitHub Actions
* collects market, financial, and news data
* generates structured research notes using LLMs
* stores outputs as Markdown and CSV for long-term tracking

---

## Core Architecture

Pipeline flow:

1. Scheduler (GitHub Actions)
2. Load watchlist (`config/watchlist.yaml`)
3. Data collection (`src/collector`)
4. AI analysis (`src/analyzer`)
5. Output generation (`src/output`)
6. Git commit & storage

---

## Strict Architectural Rules

* Maintain batch-oriented architecture (NO real-time systems)

* Preserve pipeline structure:
  collect → analyze → output

* Keep module boundaries strict:

  * collector → external data only
  * analyzer → LLM logic only
  * output → formatting & delivery only
  * utils → shared utilities

* NEVER mix responsibilities across layers

* NEVER call external APIs from analyzer/output

* NEVER put business logic in GitHub Actions YAML

---

## Cost Optimization Rules (CRITICAL)

This project is cost-constrained.

* Minimize LLM calls
* Batch requests whenever possible
* Reduce prompt size aggressively
* Avoid redundant computations
* Prefer free data sources

DO NOT:

* add unnecessary API calls
* switch to expensive models without explicit instruction
* introduce paid dependencies

---

## Data Collection Rules

* Primary:

  * yfinance → price & financials
  * RSS → news
  * DuckDuckGo → optional enrichment

* Extended (optional):

  * FMP → financial ratios, insider trading, institutional holdings, earnings surprises, dividends, peer metrics
  * Finnhub → analyst recommendation trends, peer list
  * Polygon → options flow (Max Pain, GEX, IV Skew, unusual activity)
  * SEC Form 4 → insider transactions (free fallback for FMP)
  * Technicals → RSI(14), MACD(12,26,9), Bollinger Bands (computed from yfinance history)
  * Macro → yield curve, DXY, copper via yfinance + static calendar

* Requirements:

  * implement rate limiting / delays
  * handle failures gracefully
  * normalize data before analysis

* NEVER:

  * tightly couple parsing logic with other layers
  * assume API stability

---

## Analyzer (LLM) Rules

* Input MUST be structured (no raw scraping output)

* Prompts MUST be:

  * deterministic
  * concise
  * cost-aware

* Outputs MUST be:

  * structured
  * easy to convert into Markdown

* Keep LLM provider logic isolated

* Support batching (multiple tickers per request)

---

## Output Rules

Directory structure MUST remain:

output/
├── daily/
│   └── weekly/
├── tickers/
└── data/

Rules:

* Markdown must remain Obsidian-compatible
* Output format should be deterministic
* Preserve file naming conventions
* Keep Git diffs clean and minimal

Slack / Alerts:

* optional
* must not break core pipeline

Additional Output Modules:

* json_export.py → dashboard.json, price_history.json, ticker_timelines.json, backtest_summary.json, monthly_summary.json
* alert.py → evaluates price/change alert rules from watchlist
* signal_tracker → records signals with 1D/5D/20D return tracking
* backtester → 20-day bull signal performance analysis
* API (src/api/main.py) → FastAPI REST endpoints for web/chat

---

## Configuration Rules

* All tickers MUST come from:
  config/watchlist.yaml

* NEVER hardcode:

  * tickers
  * company names
  * API keys
  * webhook URLs

* Secrets MUST come from environment variables

---

## Code Style

* Python 3.11+
* Prefer pure functions
* Use type hints where possible
* Keep functions small and readable
* Avoid overengineering

---

## Refactoring Rules

When refactoring:

* DO NOT change architecture unless explicitly asked

* DO NOT introduce:

  * databases
  * queues
  * microservices
  * web servers

* Preserve:

  * directory structure
  * output format
  * pipeline flow

Refactors should:

* improve clarity
* reduce cost
* reduce coupling

---

## Testing & Validation

Before completion:

* ensure main pipeline still works
* verify output files are correctly generated
* verify paths and structure unchanged
* ensure no secrets are logged
* ensure API calls are not increased unnecessarily
  
---

## Safe Change Policy

When making changes:

1. Read related modules first
2. Make minimal changes
3. Preserve existing behavior
4. Explain architectural impact
5. Highlight tradeoffs if any

---

## Failure Handling

* System should degrade gracefully
* If one source fails:

  * continue with remaining data
* Never fail entire pipeline unless critical

---

## Module Boundaries (Current)

```
src/
├── collector/     # External data only (price, news, filings, options, macro)
├── analyzer/      # LLM logic only (research notes, weekly insight)
├── output/        # Formatting & delivery (markdown, json, slack, obsidian, alerts)
├── utils/         # Shared utilities (config, datastore, portfolio, signals, logging)
├── api/           # FastAPI REST API server
├── backtester/    # Signal backtest engine
├── chat/          # Q&A engine over dashboard data
└── cli/           # CLI utilities (failure notification)
```

## Non-Goals

* No automated trading
* No real-time monitoring
* No overengineered infrastructure
* No expensive dependencies

---

## Completion Criteria

A task is complete only if:

* pipeline runs successfully end-to-end
* outputs are valid and readable
* architecture is preserved
* cost constraints are respected
