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

## Rules

* No coupling with analyzer
* No assumptions about API stability
* Parsing logic must remain isolated
