# Output

## Scope

The output layer turns finalized pipeline results into stable artifacts.

## Current Output Families

### Markdown

* daily note
* weekly note and structured weekly summary rendering
* per-ticker notes

### JSON For Web And Analytics

* `output/data/index.json`
* `output/data/tickers/<TICKER>/latest.json`
* `output/data/tickers/<TICKER>/history.json`
* dashboard history, price history, ticker timelines
* sector explorer payloads

Per-ticker payloads now include:
* `factor_reasoning` — surfaced from `decision/decision_layer.py` and `types.py`, written by `json_export.py`
* `ticker_macro_sensitivity` — computed for all collected tickers (not portfolio-only)

### Operational Reports

* API status
* analysis quality
* cost log
* routing outcome
* A/B test results

## Requirements

* Deterministic output structure
* Stable file naming
* Minimal unnecessary diffs
* Backward-compatible schema extensions when possible

## Constraints

* No data fetching
* No LLM calls
* No decision recomputation

## Rules

* Output formatting must consume finalized data only
* Optional delivery paths such as Slack must not become the source of truth
* Web payload shape should evolve additively unless a planned schema migration is documented
