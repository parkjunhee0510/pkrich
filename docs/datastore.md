# Datastore

## Codex Routing

- Read when the task changes persistence shape, storage timing, or backend behavior.
- Pair with `docs/state.md` for signal history and derived-state updates.
- Then inspect `src/utils/datastore.py` and related persistence callers.

## Purpose

Provide the single persistence boundary for structured pipeline data.

## Current Usage

The datastore is responsible for:
* price history queries and upserts
* signal history and signal statistics
* signal decision metadata needed by shadow analysis-performance outputs
* analysis run metadata
* backend-specific persistence details hidden from callers

## Backends

### CSV

* simple and transparent
* useful for exported artifacts and compatibility flows

### SQLite

* preferred for indexed queries and growing history
* used by runtime features that need efficient lookups
* preserves the same signal-history metadata columns as the CSV signal tracker

## Selection

* Backend selection is configuration-driven
* Callers must use datastore APIs, not backend files directly

## Rules

* Output, analyzer, and decision code must not issue direct SQLite queries against shared datastore backends
* Risk Intelligence may use `output/data/risk_intel.sqlite` as an output-local canonical store for its graph/export contract, owned by `src/output/risk_intel_store.py`; this DB must not be used as the general datastore boundary or mirrored to web public data
* No direct CSV mutation outside datastore helpers
* Backend choice must not change business semantics
