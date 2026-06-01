# Data Collection

## Codex Routing

- Read when the task changes external data sources, provider fallback chains, or normalization before analysis.
- Pair with `docs/pipeline.md` only if collect-stage handoff or runtime order changes.
- Then inspect `src/collector/` and related provider config.

## Sources

### Primary

* yfinance
* RSS feeds
* DuckDuckGo

### Optional

* FMP
* Finnhub
* Polygon
* SEC EDGAR

## Fallback Strategy

* Primary → Secondary → Tertiary sources
* Each source must degrade gracefully

## Requirements

### Reliability

* Retry on failure
* Do not crash pipeline

### Rate Limiting

* Respect API limits
* Add delays between calls
* `RateLimiterHub` owns provider token buckets and can also register LLM request/token buckets for paths that need RPM and TPM throttling

### Normalization

* Convert all inputs into structured format
* Ensure consistency across sources

## Peer Metrics

* Primary: `yfinance_peer_metrics.py` (yfinance)
* Fallback: FMP provider
* `peer_selection_cache` includes poisoning guards to prevent stale or corrupt fallback entries from overriding good primary results

## Macro v2 Sources

* `macro_surprise.py` — economic surprise index collection
* `macro_events.py` — scheduled macro events (FOMC, CPI, NFP, etc.)
* Consumed by `decision/factors/macro_regime_factor.py` and `decision/factors/macro_event_factor.py` via `utils/macro_event_match.py`

## Search Evidence

Search evidence is a collector-owned enrichment path. PR 1 is cache-backed and provider-independent: it reads structured files from `output/cache/search_evidence/<YYYY-MM-DD>/<TICKER>.json`, normalizes them, and emits a valid search evidence payload without making live provider calls. The collector first checks the run-date cache and may reuse the latest prior daily cache inside `cache_ttl_hours`; reused prior caches are recorded with `cache_source_date`, `cache_age_hours`, and `run_summary.stale_cache_hit_count`.

OpenAI Web Search integration plugs into this same collector boundary through `config/search_evidence.yaml` and `src/collector/providers/search/openai_web_search.py`. The committed default mode is `openai`, so normal pipeline runs refresh priority search evidence when `OPENAI_API_KEY` is available. Live refresh calls are still capped by `max_search_tickers_per_run`, query limits, rate limits, and BudgetGuard telemetry. Operators can set `SEARCH_EVIDENCE_MODE=cache` or `mode: cache` for an offline/cache-only run; when `openai` mode is selected without a usable provider, the artifact records `provider_unavailable` instead of silently reporting a cache-only zero-coverage run.

#### Priority Evidence Refresh

Smart Router `selected_tickers` define the V1 priority evidence refresh pool. The collector owns this priority metadata and reorders candidates after cache lookup using explicit reason codes: `router_selected`, `no_evidence`, `not_refreshed`, `stale_cache`, `portfolio_holding`, `important_action`, and `high_volatility`.

Cache mode records `priority_for_refresh`, `priority_refresh_reasons`, priority status counts, and priority refresh candidate counts without making provider calls. OpenAI mode refreshes priority tickers before non-priority tickers, then applies the existing provider cap through `max_search_tickers_per_run` and the existing query limits. Provider failures remain separate from true no-evidence statuses so downstream health checks can distinguish operational gaps from low evidence coverage.

The normalized `by_ticker` summary includes `evidence_status`, `provider_status`, `priority_for_refresh`, `priority_refresh_reasons`, `cache_source_date`, and `cache_age_hours` so downstream layers can distinguish true missing evidence from operational gaps and stale-but-usable cached evidence. Current `evidence_status` values include `covered`, `no_evidence`, `not_refreshed`, `provider_unavailable`, `provider_error`, and `cache_error`. `run_summary.priority_tickers` records the normalized candidate tickers that were requested for priority refresh, while `run_summary.priority_refresh_reasons`, `run_summary.priority_status_counts`, `run_summary.priority_refresh_candidate_count`, `run_summary.cache_ttl_hours`, `run_summary.stale_cache_hit_count`, and `run_summary.status_counts` aggregate priority targeting, cache policy, stale reuse, and evidence statuses for output health and review.

`performance_baseline.json` derives a read-only Search evidence provider readiness track from this normalized payload. It records provider call/error/cache-error/skipped counts, cap review status, priority candidate ratio, provider issue status, operational issue count, and stale-cache reuse status. These fields are review telemetry only; they do not switch `mode`, raise `max_search_tickers_per_run`, or make provider calls.

Analyzer, decision, output, and web code must consume normalized search evidence only; they must not call web search directly.

## Rules

* No coupling with analyzer
* No assumptions about API stability
* Parsing logic must remain isolated
