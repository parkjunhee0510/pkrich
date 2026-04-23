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
* analysis run metadata
* backend-specific persistence details hidden from callers

## Backends

### CSV

* simple and transparent
* useful for exported artifacts and compatibility flows

### SQLite

* preferred for indexed queries and growing history
* used by runtime features that need efficient lookups

## Selection

* Backend selection is configuration-driven
* Callers must use datastore APIs, not backend files directly

## Rules

* No direct SQLite queries from output, analyzer, or decision code
* No direct CSV mutation outside datastore helpers
* Backend choice must not change business semantics
