# Risk Intelligence SQLite + JSON Export Hybrid Design

Date: 2026-05-19
Status: Draft for user review
Owner: Codex

## Summary

Risk Intelligence should move from JSON-as-canonical storage to a SQLite canonical store with materialized JSON exports.

SQLite becomes the internal source of truth for graph entities, relationships, evidence records, alert paths, manual refresh patches, and export manifests. The existing JSON artifacts remain the frontend and output contract:

- `output/data/risk_intel_graph.json`
- `output/data/risk_intel_summary.json`
- `output/data/risk_intel_refresh_log.json`

The frontend continues to read JSON only. SQLite is not copied to `web/public/data` and is not exposed directly to the browser.

## Context

The current Risk Intelligence graph is already richer than a simple document:

- Nodes, edges, evidence records, domain rules, input status, alert paths, health warnings, and duplicate candidates live in one graph artifact.
- Summary cards are derived from alert paths and are consumed by the dashboard.
- Health checks validate score math, caps, guardrails, inference references, stale domain rules, run IDs, and artifact consistency.
- Manual refresh is expected to create patch candidates before the next daily batch absorbs them into a canonical graph.

JSON is still useful as a portable output format, but it is becoming fragile as the canonical write model.

## Problems With JSON As Canonical Storage

JSON has several structural weaknesses for this feature:

- Relationship queries require repeated full-file scans.
- Referential integrity is enforced only by custom health code.
- Manual refresh patch lifecycle is awkward because patch candidates, validation results, and applied states are not naturally transactional.
- Historical comparison requires either many full snapshots or ad hoc file naming.
- Concurrent or partial writes can produce invalid artifacts unless every writer is very careful.
- Index-like access patterns, such as top alerts by ticker or all paths from one issue, get slower as graph size grows.

## Decision

Use Option B: SQLite canonical store plus JSON materialized export.

The daily batch builds normalized Risk Intelligence records, writes one run transaction into SQLite, then exports deterministic JSON artifacts from SQLite.

The JSON files remain stable public artifacts. SQLite exists to make internal generation, validation, patching, and future querying more reliable.

## Goals

- Preserve the existing JSON frontend contract.
- Make graph relationships queryable without full JSON scans.
- Add database-level uniqueness and foreign-key style validation where practical.
- Support manual refresh patch candidates without directly mutating canonical JSON.
- Store export manifests so health checks can prove which DB run produced which JSON artifact.
- Keep the daily pipeline dependency-light and compatible with GitHub Actions.
- Avoid any cost increase.

## Non-Goals

- No graph database in this phase.
- No PostgreSQL, Redis, or server-side hosted database in this phase.
- No direct frontend access to SQLite.
- No browser-side SQL or WASM database.
- No real-time updates.
- No FastAPI query endpoint in this phase.
- No admin UI for manual patch review in this phase.
- No external Tier 2 web search provider calls in the daily batch.
- No change to official investment decision logic.

## Data Flow

The proposed generation flow is:

1. Existing collectors and analyzers produce Risk Intelligence inputs.
2. The Risk Intelligence builder creates typed in-memory graph records.
3. The SQLite store replaces the current run in one transaction.
4. The exporter reads the latest run from SQLite.
5. The exporter writes the three existing JSON artifacts.
6. Export manifests are written back to SQLite with file hash, size, path, and run ID.
7. Existing web sync copies JSON artifacts to `web/public/data`.
8. Output health checks validate both JSON and SQLite consistency.

SQLite is therefore canonical for Risk Intelligence internals, while JSON is canonical for the public output contract.

## Storage Location

Default SQLite path:

```text
output/data/risk_intel.sqlite
```

The generated SQLite file is a runtime artifact. This design does not require committing the generated DB file.

## SQLite Settings

Use conservative SQLite settings:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA user_version = 1;
```

WAL improves local write reliability and read performance. If GitHub Actions artifact handling becomes simpler with rollback journal mode, the implementation may switch journal mode while keeping the same schema.

After a successful export, the writer must close the DB connection and run `PRAGMA wal_checkpoint(TRUNCATE)` before treating `risk_intel.sqlite` as a complete generated artifact. SQLite sidecar files such as `risk_intel.sqlite-wal` and `risk_intel.sqlite-shm` are transient and must not be mirrored to `web/public/data`.

## Schema

### risk_intel_runs

Stores one row per generated Risk Intelligence run.

```sql
CREATE TABLE risk_intel_runs (
  run_id TEXT PRIMARY KEY,
  as_of TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ok', 'partial', 'degraded', 'error')),
  schema_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  scoring_config_version TEXT NOT NULL,
  confidence_config_version TEXT NOT NULL,
  source_config_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_risk_intel_runs_as_of ON risk_intel_runs(as_of);
CREATE INDEX idx_risk_intel_runs_status ON risk_intel_runs(status);
```

### risk_intel_nodes

Stores graph nodes for one run.

```sql
CREATE TABLE risk_intel_nodes (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  canonical_id TEXT NOT NULL,
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  label_ko TEXT NOT NULL,
  summary_ko TEXT NOT NULL,
  status TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_nodes_canonical ON risk_intel_nodes(run_id, canonical_id);
CREATE INDEX idx_risk_intel_nodes_type ON risk_intel_nodes(run_id, node_type);
```

### risk_intel_edges

Stores graph edges for one run.

```sql
CREATE TABLE risk_intel_edges (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  relationship TEXT NOT NULL,
  relationship_label_ko TEXT NOT NULL,
  evidence_type TEXT NOT NULL CHECK (evidence_type IN ('explicit', 'inferred', 'social', 'market')),
  evidence_label_ko TEXT NOT NULL,
  confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  severity_delta REAL NOT NULL CHECK (severity_delta >= -1.0 AND severity_delta <= 1.0),
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  inference_refs_json TEXT NOT NULL DEFAULT '[]',
  explanation_ko TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_edges_source ON risk_intel_edges(run_id, source_id);
CREATE INDEX idx_risk_intel_edges_target ON risk_intel_edges(run_id, target_id);
CREATE INDEX idx_risk_intel_edges_type ON risk_intel_edges(run_id, evidence_type);
CREATE INDEX idx_risk_intel_edges_source_target ON risk_intel_edges(run_id, source_id, target_id);
```

Node-reference validation for `source_id` and `target_id` remains in health checks rather than SQLite foreign keys because run-scoped graph imports may insert records in any order.

### risk_intel_source_records

Stores source and market evidence records.

```sql
CREATE TABLE risk_intel_source_records (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  trust_tier TEXT NOT NULL,
  published_at TEXT NOT NULL,
  url TEXT,
  title TEXT NOT NULL,
  title_ko TEXT NOT NULL,
  summary_ko TEXT NOT NULL,
  target_id TEXT,
  reaction_type TEXT,
  reaction_strength TEXT CHECK (
    reaction_strength IS NULL OR reaction_strength IN ('strong', 'moderate', 'weak', 'none')
  ),
  reaction_score REAL CHECK (reaction_score IS NULL OR (reaction_score >= 0.0 AND reaction_score <= 1.0)),
  metric TEXT,
  value REAL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_source_records_trust ON risk_intel_source_records(run_id, trust_tier);
CREATE INDEX idx_risk_intel_source_records_type ON risk_intel_source_records(run_id, source_type);
CREATE INDEX idx_risk_intel_source_records_target ON risk_intel_source_records(run_id, target_id);
```

### risk_intel_domain_rules

Stores domain inference rules used by inferred edges.

```sql
CREATE TABLE risk_intel_domain_rules (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  version TEXT NOT NULL,
  source_type TEXT NOT NULL,
  title TEXT NOT NULL,
  title_ko TEXT NOT NULL,
  rationale_ko TEXT NOT NULL,
  rule_confidence REAL NOT NULL CHECK (rule_confidence >= 0.0 AND rule_confidence <= 1.0),
  last_reviewed TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_domain_rules_reviewed ON risk_intel_domain_rules(run_id, last_reviewed);
```

### risk_intel_input_status

Stores input availability and freshness for health status calculation.

```sql
CREATE TABLE risk_intel_input_status (
  run_id TEXT NOT NULL,
  name TEXT NOT NULL,
  path TEXT,
  tier INTEGER NOT NULL,
  required INTEGER NOT NULL CHECK (required IN (0, 1)),
  status TEXT NOT NULL CHECK (
    status IN ('present', 'missing', 'skipped_not_enabled', 'provider_error', 'cache_only', 'stale')
  ),
  record_count INTEGER NOT NULL,
  as_of TEXT,
  PRIMARY KEY (run_id, name),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_input_status_required ON risk_intel_input_status(run_id, required, status);
```

### risk_intel_alert_paths

Stores scored alert paths. Complex nested values remain JSON text for Phase 1.5 to avoid over-normalizing a still-evolving explanation contract.

```sql
CREATE TABLE risk_intel_alert_paths (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  canonical_issue_id TEXT NOT NULL,
  target_group_type TEXT NOT NULL CHECK (target_group_type IN ('sector', 'ticker')),
  target_group_id TEXT NOT NULL,
  representative_target_id TEXT NOT NULL,
  alert_level TEXT NOT NULL CHECK (alert_level IN ('observation', 'warning', 'alert')),
  alert_level_label_ko TEXT NOT NULL,
  raw_score REAL NOT NULL CHECK (raw_score >= 0.0 AND raw_score <= 1.0),
  score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
  score_kind TEXT NOT NULL CHECK (score_kind IN ('final', 'capped_final')),
  cap_value REAL CHECK (cap_value IS NULL OR (cap_value >= 0.0 AND cap_value <= 1.0)),
  score_breakdown_json TEXT NOT NULL,
  caps_applied_json TEXT NOT NULL DEFAULT '[]',
  guardrails_applied_json TEXT NOT NULL DEFAULT '[]',
  path_node_ids_json TEXT NOT NULL,
  path_edge_ids_json TEXT NOT NULL,
  affected_sector_ids_json TEXT NOT NULL DEFAULT '[]',
  affected_ticker_ids_json TEXT NOT NULL DEFAULT '[]',
  affected_ticker_details_json TEXT NOT NULL DEFAULT '[]',
  aggregation_json TEXT NOT NULL,
  evidence_counts_json TEXT NOT NULL DEFAULT '{}',
  top_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  inference_refs_json TEXT NOT NULL DEFAULT '[]',
  edge_evidence_types_json TEXT NOT NULL DEFAULT '[]',
  rationale_ko TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_alert_paths_issue ON risk_intel_alert_paths(run_id, canonical_issue_id);
CREATE INDEX idx_risk_intel_alert_paths_target ON risk_intel_alert_paths(run_id, target_group_type, target_group_id);
CREATE INDEX idx_risk_intel_alert_paths_level_score ON risk_intel_alert_paths(run_id, alert_level, score DESC);
```

### risk_intel_health_warnings

Stores non-fatal health warnings that should appear in exported graph metadata.

```sql
CREATE TABLE risk_intel_health_warnings (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('info', 'warning')),
  message_ko TEXT NOT NULL,
  ref_type TEXT,
  ref_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_health_warnings_run ON risk_intel_health_warnings(run_id, code);
```

Minimum warning producers:

- A non-observation alert path references a stale domain rule.
- Any input status is `cache_only` or `stale`.
- `pending_duplicate_candidates` is not empty.

If a non-observation alert path references a stale domain rule, the run status is `degraded`.

### risk_intel_pending_duplicate_candidates

Stores alias-resolution candidates for manual review.

```sql
CREATE TABLE risk_intel_pending_duplicate_candidates (
  run_id TEXT NOT NULL,
  new_candidate_id TEXT NOT NULL,
  matched_canonical_id TEXT NOT NULL,
  similarity_score REAL NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
  status TEXT NOT NULL CHECK (status IN ('pending', 'merged', 'rejected', 'expired')),
  detected_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT,
  PRIMARY KEY (run_id, new_candidate_id, matched_canonical_id),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_intel_duplicate_candidates_status
  ON risk_intel_pending_duplicate_candidates(run_id, status);
```

### risk_intel_export_manifest

Stores deterministic export metadata for each JSON artifact.

```sql
CREATE TABLE risk_intel_export_manifest (
  run_id TEXT NOT NULL,
  artifact_name TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  exported_at TEXT NOT NULL,
  PRIMARY KEY (run_id, artifact_name),
  FOREIGN KEY (run_id) REFERENCES risk_intel_runs(run_id) ON DELETE CASCADE
);
```

Expected `artifact_name` values:

- `risk_intel_graph`
- `risk_intel_summary`
- `risk_intel_refresh_log`

### risk_intel_refresh_requests

Stores manual refresh patch lifecycle data. Refresh results never directly overwrite the canonical graph.

```sql
CREATE TABLE risk_intel_refresh_requests (
  refresh_id TEXT PRIMARY KEY,
  base_graph_run_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  patch_status TEXT NOT NULL CHECK (patch_status IN ('pending', 'applied', 'rejected', 'expired')),
  patch_candidate_json TEXT NOT NULL,
  validation_result_json TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  applied_run_id TEXT,
  review_note TEXT
);

CREATE INDEX idx_risk_intel_refresh_requests_base
  ON risk_intel_refresh_requests(base_graph_run_id, patch_status);
```

Patch candidates are absorbed only by a later daily batch. The exported refresh log remains the UI-facing representation.

## JSON Export Contract

The exported JSON shape remains compatible with the current Risk Intelligence artifacts.

The exporter must preserve:

- `schema_version`
- `as_of`
- `status`
- `generation.run_id`
- `generation.scoring_config_version`
- `generation.confidence_config_version`
- `nodes`
- `edges`
- `source_records`
- `domain_rules`
- `input_status`
- `pending_duplicate_candidates`
- `health_warnings`
- `alert_paths`
- summary cards with Korean labels and Korean copy
- refresh log patch lifecycle fields

Summary cards are not a canonical table in Phase 1.5. They are derived from `risk_intel_alert_paths` during export using the existing dedupe, sort, and top-N rules.

## Health Checks

Existing JSON health checks remain required.

Add SQLite-backed validation:

- SQLite file exists when Risk Intelligence JSON artifacts exist after the migration is enabled.
- `PRAGMA integrity_check` returns `ok`.
- Required tables exist.
- A latest run exists.
- JSON artifact `generation.run_id` values match the latest exported DB run.
- Manifest file hashes and byte sizes match actual JSON files.
- JSON counts match SQLite row counts for nodes, edges, source records, domain rules, input status, duplicate candidates, and alert paths.
- Every edge `source_id` and `target_id` resolves to a node in the same run.
- Every edge `evidence_refs` item resolves to a source record in the same run.
- Every inferred edge `inference_refs` item resolves to a domain rule in the same run.
- Every alert path edge and node reference resolves in the same run.
- Every alert path weighted score matches `raw_score` within `0.01`.
- If caps are applied, final `score` is at or below `cap_value`.
- If no caps are applied, final `score` matches `raw_score` within `0.01`.
- Confidence band validation still runs by evidence type.
- SQLite is not mirrored to `web/public/data`.

## Failure Policy

SQLite write and export should be transactional from the perspective of a run:

- If the DB write fails, do not export partially derived Risk Intelligence JSON.
- If JSON export fails, record the failure and keep the previous valid artifacts when possible.
- If both DB and JSON export fail for the current run, write a minimal `error` status artifact only when the existing output health conventions require a JSON file.
- Web mirror failure is non-fatal and should be reported as a warning.

The implementation should not silently fall back to builder-direct JSON after SQLite becomes canonical, because that would hide DB corruption or migration bugs.

## Performance Rationale

SQLite is the best fit for this repository's constraints:

- Local embedded database with no server dependency.
- Fast indexed reads for issue, ticker, sector, alert level, and score queries.
- Atomic run replacement.
- Strong enough integrity checks without introducing infrastructure.
- Better write and query performance than repeatedly loading large JSON files.
- Much simpler operational model than PostgreSQL or a graph database.

Expected query patterns and indexes:

- Latest run by `as_of`: `idx_risk_intel_runs_as_of`.
- Top alerts by level and score: `idx_risk_intel_alert_paths_level_score`.
- All alert paths for one issue: `idx_risk_intel_alert_paths_issue`.
- All alert paths for one ticker or sector: `idx_risk_intel_alert_paths_target`.
- Edge expansion from a node: `idx_risk_intel_edges_source` and `idx_risk_intel_edges_target`.
- Evidence filtering by source type or trust tier: source record indexes.

## Migration Plan

1. Add SQLite store module with schema creation and run replacement.
2. Add exporter module that reconstructs the current JSON artifacts from SQLite.
3. Add roundtrip tests comparing builder output to SQLite-exported JSON.
4. Switch Risk Intelligence JSON generation to builder -> SQLite -> exporter.
5. Add SQLite manifest and health checks.
6. Keep frontend unchanged except for any required type compatibility fixes.
7. Update output documentation to describe SQLite as the internal canonical store and JSON as the public contract.

## Testing

Required tests:

- Store schema creation is idempotent.
- One run can be written and loaded.
- Rewriting the same run does not duplicate rows.
- Exported graph JSON preserves current required fields.
- Exported summary JSON preserves Korean labels and card structure.
- Exported refresh log preserves patch lifecycle fields.
- Manifest hashes match exported files.
- Missing edge node references fail health checks.
- Missing evidence refs fail health checks.
- Missing inference refs fail health checks.
- Stale domain rule used by a non-observation alert path marks the run `degraded`.
- `cache_only` or `stale` input status creates a health warning.
- Pending duplicate candidates create a health warning.
- Confidence bands are validated by evidence type.
- SQLite is not copied to `web/public/data`.
- Daily batch path does not call external Tier 2 providers.

## Acceptance Criteria

- Risk Intelligence writes a SQLite store at `output/data/risk_intel.sqlite`.
- The three existing JSON artifacts are still written with compatible schemas.
- The frontend continues to render from JSON only.
- The SQLite DB has one latest run with nodes, edges, source records, domain rules, input status, alert paths, health warnings, duplicate candidates, and export manifests.
- Output health validates SQLite integrity and JSON export consistency.
- Manual refresh patch candidates have a DB-backed lifecycle table.
- Summary cards are still derived, deduped, sorted, and labeled in Korean.
- Existing calibration fixtures still pass.
- No external Tier 2 provider is called during the daily batch.
- Official investment decisions are unchanged.
- Pipeline runtime remains suitable for the current GitHub Actions workflow.

## Deferred Decisions

These are intentionally out of scope for this phase:

- Whether to expose a future local query API over SQLite.
- Whether to add normalized join tables for every JSON array.
- Whether manual duplicate resolution needs a UI.
- Whether historical runs should be retained indefinitely or pruned after a retention window.
- Whether a future hosted deployment should migrate from SQLite to PostgreSQL.

The current design keeps those paths open without requiring them now.
