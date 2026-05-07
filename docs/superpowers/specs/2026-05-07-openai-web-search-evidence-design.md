# OpenAI Web Search Evidence System Design

## Status

Approved for spec review on 2026-05-07.

## Context

The stock research pipeline already has a mature batch flow:

```text
collect -> analyze -> state -> output -> store -> log
```

The current system collects market data, news, macro, policy, and portfolio context; runs deterministic analyzer modules and cost-aware LLM passes; generates rule-based decisions; writes Markdown/JSON outputs; syncs web-facing payloads; and records operational telemetry.

Recent improvements added:

- data quality scoring and shadow quality gates
- BudgetGuard telemetry for optional LLM paths
- LLM evidence manifests
- action change feed and today decision strip
- output JSON and web-public sync health checks

The next opportunity is to improve research evidence quality with OpenAI Web Search. The feature should not turn the pipeline into a real-time trading system, should not make the web app a source of business logic, and should not let search results directly override official rule-based decisions. Search should be a controlled evidence layer that improves coverage, auditability, and dashboard trust signals.

OpenAI Web Search API details, model/tool identifiers, and current pricing must be verified against official OpenAI documentation immediately before implementation of the real provider. This design intentionally keeps the first phase provider-independent so tests and CI can run without API access.

## Goals

- Add a standard search evidence contract that can later be backed by OpenAI Web Search.
- Improve recommendation quality by identifying when a strong action has weak or stale evidence.
- Audit LLM claims against recent external web evidence before search affects official actions.
- Surface compact evidence quality signals in the web dashboard.
- Keep costs bounded through trigger-based routing, cache reuse, and BudgetGuard telemetry.
- Preserve current layer boundaries: external search belongs to the collector side, not the analyzer, decision, output, or web layers.
- Keep the first implementation testable without a live OpenAI API key.

## Non-Goals

- No live OpenAI Web Search API call in PR 1.
- No immediate official action changes in PR 1.
- No real-time search, alerting, or trading automation.
- No broad rewrite of collector, analyzer, decision, or dashboard architecture.
- No raw prompt, full provider response, API key, or sensitive environment value in output artifacts.
- No web UI recomputation of decisions from search results.
- No schema-breaking changes to existing output payloads.

## Accepted Approach

Use a shared Search Evidence Layer and connect A/B/C use cases in phases.

The accepted approach covers all three desired outcomes:

- A. Recommendation accuracy improvement
- B. Evidence and hallucination audit
- C. Dashboard evidence display

But it does not implement all effects at once. The pipeline first gets a stable search evidence schema, cache shape, output writer, health checks, and tests. Later phases connect audit, decision metadata, UI badges, and finally the real OpenAI Web Search provider.

```text
Search evidence input/cache
        |
        v
Collector-owned Search Evidence Layer
        |
        v
output/data/search_evidence.json
        |
        +--> Search Audit
        +--> data_quality_score metadata
        +--> Dashboard evidence badges
```

This keeps one source of search truth instead of scattering search calls across analyzer prompts, decision scoring, and frontend code.

## Architecture

### Collector-Owned Search Evidence

Search evidence lives under the collector boundary because it depends on an external API.

Initial source modules:

```text
src/collector/search_evidence.py
src/collector/providers/search/openai_web_search.py
```

PR 1 should create the provider-independent contract and a cache/mock loader. The OpenAI-backed provider is deferred until PR 5.

Collector output should be normalized before analyzer or decision code consumes it. Downstream layers should only see structured search evidence records and aggregate quality scores.

### Output Artifacts

Primary web-facing artifact:

```text
output/data/search_evidence.json
web/public/output/data/search_evidence.json
```

Future audit artifact:

```text
output/data/search_audit.json
web/public/output/data/search_audit.json
```

Raw provider responses are not web-facing artifacts. Cache files, if used, live under:

```text
output/cache/search_evidence/<YYYY-MM-DD>/<TICKER>.json
```

The cache stores structured summaries and source metadata, not raw provider payloads.

### Web Sync

`output/data` remains the source of truth. `web/public/output/data` is a mirror only. The output health check should include the new search evidence artifacts once they exist.

## Data Contract

### `search_evidence.json`

The first stable payload should be additive and schema-versioned:

```json
{
  "schema_version": 1,
  "date": "2026-05-07",
  "generated_at": "2026-05-07T09:00:00+09:00",
  "provider": "cache",
  "items": [
    {
      "ticker": "COHR",
      "query": "COHR latest earnings AI datacenter optical revenue",
      "source_domain": "coherent.com",
      "title": "Coherent reports fiscal results",
      "url": "https://example.com/cohr-results",
      "published_at": "2026-05-04",
      "snippet": "Short structured evidence summary.",
      "evidence_type": "earnings",
      "relevance_score": 0.88,
      "freshness_hours": 72,
      "query_hash": "sha256:..."
    }
  ],
  "by_ticker": {
    "COHR": {
      "coverage_score": 0.74,
      "source_diversity": 3,
      "freshness_score": 0.8,
      "evidence_count": 5,
      "top_domains": ["coherent.com", "sec.gov", "reuters.com"]
    }
  },
  "run_summary": {
    "candidate_ticker_count": 5,
    "searched_ticker_count": 0,
    "cache_hit_count": 5,
    "provider_call_count": 0,
    "skipped_ticker_count": 0
  }
}
```

PR 1 can use `"provider": "cache"` or `"provider": "fixture"` because no live OpenAI call is included.

### Future `search_audit.json`

The audit payload should compare important analysis claims with available evidence:

```json
{
  "schema_version": 1,
  "date": "2026-05-07",
  "tickers": [
    {
      "ticker": "MOD",
      "verdict": "warn",
      "checked_claims": 6,
      "supported_claims": 4,
      "conflicting_claims": 1,
      "missing_evidence_claims": 1,
      "issues": [
        {
          "claim": "Data center revenue grew 78%",
          "status": "supported",
          "source_url": "https://example.com/mod-results"
        }
      ]
    }
  ]
}
```

The audit starts as observational. It should not directly change official actions.

## Search Triggers

Search must be trigger-based, not applied to every ticker every run.

Initial candidate triggers:

- action changed since prior run
- `NEW BUY` or `BUY` candidate
- conviction moved by at least 15 points
- `data_quality_score < 0.65`
- low news coverage or source diversity
- newly added watchlist ticker
- current holding with newly added risk

Initial conservative limits:

```text
max_search_tickers_per_run: 5
max_queries_per_ticker: 2
cache_ttl_hours: 24
```

The exact config file can be decided during implementation, but the behavior should be owned by model/cost configuration rather than hard-coded in many call sites.

## Decision Integration

Search should first reduce overconfidence, not create aggressive buy signals.

Preferred initial policy:

```text
Good evidence may slightly improve confidence metadata.
Weak evidence may cap an otherwise strong BUY to WATCH only after shadow telemetry is reviewed.
Missing search due to provider failure should not penalize a ticker.
```

PR 3 should start in shadow mode:

```json
{
  "search_evidence_score": 0.48,
  "search_quality_gate": {
    "would_cap_action": true,
    "reason": "low recent source coverage"
  }
}
```

Partial enforce can be considered later:

```python
if action == "buy" and search_evidence_score < 0.55:
    max_action = "watch"
```

## Dashboard Integration

The dashboard should show compact evidence quality signals, not long article feeds.

Preferred first UI placements:

1. Action Change Feed
2. Today Decision Strip
3. Ticker Detail

Example display:

```text
Evidence: Strong
Sources: 4
Freshness: 12h
Audit: 5/6 supported
Risk: valuation concern newly detected
```

The UI must consume output payloads only. It must not perform search, recompute official actions, or call providers.

## Budget And Failure Policy

Search should be guarded like optional expensive LLM paths.

Future BudgetGuard paths:

```text
search_evidence
search_audit
```

Default mode should be `shadow`. Enforce mode can come later after cost and quality telemetry are understood.

Failure behavior:

- Provider unavailable: emit warning and continue.
- Search timeout: use cached evidence if valid; otherwise mark search unavailable.
- No evidence found: return empty evidence with low coverage, but distinguish this from provider failure.
- API error: do not penalize data quality solely because the provider failed.
- Cache corruption: ignore bad cache entry and log an output/collector warning.

## Phased Delivery

### PR 1: Search Evidence Contract, Cache, Output, Health Check

Included:

- provider-independent search evidence models/helpers
- cache or fixture loading path
- `output/data/search_evidence.json`
- web-public mirror sync
- output health check coverage
- docs updates
- tests for schema, cache behavior, and output sync

Excluded:

- live OpenAI API call
- decision action change
- dashboard UI changes

### PR 2: Search Audit Output

Included:

- claim extraction from existing analysis fields
- observational audit result
- `output/data/search_audit.json`
- tests for supported, conflicting, missing, and insufficient-evidence cases

### PR 3: Data Quality Shadow Integration

Included:

- `search_evidence_score`
- `search_quality_gate`
- shadow-only `would_cap_action`
- tests proving official action remains unchanged in shadow mode

### PR 4: Dashboard Evidence Badges

Included:

- Action Change Feed evidence badges
- Today Decision Strip evidence summary
- Ticker Detail evidence panel or compact section
- frontend tests for missing/partial/strong evidence states

### PR 5: OpenAI Web Search Provider

Included:

- official OpenAI Web Search API provider
- rate limiting
- query templates
- cache TTL
- BudgetGuard telemetry
- mocked provider tests

OpenAI API parameter names, model/tool identifiers, and pricing assumptions must be verified against official OpenAI documentation before this PR starts.

### PR 6: Partial Enforce Policy

Included only after shadow telemetry review:

- optional quality gate that caps weak-evidence BUY to WATCH
- config-driven enforce mode
- audit and output explanations for capped actions

## Testing

PR 1 tests:

- search evidence model serializes stable JSON
- cache/fixture provider returns normalized records
- empty evidence emits a valid payload
- output writer includes `schema_version`
- web-public mirror receives `search_evidence.json`
- `python -m src.cli.output_health_check` validates the new mirror file

Future tests:

- search audit supported/conflicting/missing evidence cases
- decision shadow mode does not alter official action
- enforce mode caps only configured actions
- dashboard renders strong, weak, missing, and unavailable evidence states
- provider failure does not fail the full pipeline

Baseline validation:

```text
python -m compileall main.py src tests
python -m pytest tests/test_search_evidence.py tests/test_output_health_check.py
python -m src.cli.output_health_check
```

Add broader pipeline and web tests when UI or decision integration begins.

## Open Questions Deferred To Implementation Planning

- Exact config location for search trigger limits.
- Whether PR 1 should include only fixture input or also cache read/write helpers.
- Exact claim extraction rules for PR 2.
- Exact dashboard badge copy and placement.
- Exact OpenAI Web Search API request shape after official docs verification.

These are implementation details, not blockers for the phased architecture.
