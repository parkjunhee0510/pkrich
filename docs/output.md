# Output

## Codex Routing

- Read when the task changes exported markdown, JSON schema, frontend payloads, or output stability rules.
- Pair with `docs/datastore.md` only if output depends on stored shape or backfilled history.
- Then inspect `src/output/` and `web/src/` only when the frontend consumes changed data.

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
* `factor_reasoning` surfaced from `decision/decision_layer.py` and `types.py`, written by `json_export.py`
* `ticker_macro_sensitivity` computed for all collected tickers, not portfolio-only
* `committee_analysis` for always-visible committee debate summaries plus PM conclusions
* the web dashboard and ticker detail UI consume `committee_analysis` as a presentation-layer debate record, separate from the official `decision`

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
* Committee output is presentation data and must not override rule-based `buy/watch/avoid`
