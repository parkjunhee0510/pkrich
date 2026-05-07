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

Search evidence is a collector-owned enrichment path. PR 1 is cache-backed and provider-independent: it reads structured files from `output/cache/search_evidence/<YYYY-MM-DD>/<TICKER>.json`, normalizes them, and emits a valid search evidence payload without making live provider calls.

OpenAI Web Search integration plugs into this same collector boundary through `config/search_evidence.yaml` and `src/collector/providers/search/openai_web_search.py`. The default mode is still `cache`, so normal pipeline runs do not make live search calls. Switching `mode: openai` requires `OPENAI_API_KEY`, rate limits, BudgetGuard telemetry, and current official OpenAI Web Search API verification.

Analyzer, decision, output, and web code must consume normalized search evidence only; they must not call web search directly.

## Rules

* No coupling with analyzer
* No assumptions about API stability
* Parsing logic must remain isolated
