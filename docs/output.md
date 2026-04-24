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
* `pm_view` on the latest index payload and each `dashboard_history.days[]` entry for additive PM review context on held names

`pm_view` is a review-oriented payload for the web UI. It is additive and must not override the official rule-based `buy` / `watch` / `avoid` decision.

Current `pm_view` fields:
* `as_of`
* `swap_candidates[]` with `held_ticker`, `candidate_ticker`, `swap_candidate_score`, `summary`, `reasons`, `overlap_context`, `review_points`
* `event_exposure_items[]` with `ticker`, `event_risk_score`, `event_label`, `event_date`, `days_until`, `summary`, `reasons`, `review_points`
* `today_priority_queue[]` with `priority_type`, `ticker`, `related_ticker`, `today_priority_score`, `summary`, `reasons`, `destination`
* `empty_states` for empty-safe frontend rendering

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
* `pm_view` is presentation data for portfolio review surfaces and must not reinterpret or replace official `buy/watch/avoid`
