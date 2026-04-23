# Architecture

## Codex Routing

- Read first only when the task is about layer boundaries or deciding which architecture doc to open.
- For decision logic, go to `docs/decision.md`.
- For shared helper behavior, go to `docs/utils.md`.

## Principles

* Batch-first design
* Strict separation of concerns
* Deterministic outputs
* Cost-aware execution
* One storage boundary through datastore

## Document Map

- `docs/decision.md`: factor scoring, conviction, regime-aware decision rules
- `docs/utils.md`: shared helpers that support multiple layers without owning workflows
- `docs/pipeline.md`: choose the right pipeline-level doc before reading runtime details

## Layer Overview

- `collector/`: external data fetching, fallback chains, normalized handoff
- `analyzer/`: structured LLM analysis, module orchestration, deterministic fallback
- `decision/`: rule-based conviction scoring and final action generation
- `state/`: reproducible signal history and derived outcomes
- `output/`: deterministic Markdown and JSON artifacts
- `datastore/`: single persistence boundary across CSV and SQLite
- `logging/`: step-level execution and operational diagnostics
- `utils/`: shared helpers that support layers without becoming a hidden workflow layer

## Current End-To-End Shape

The current production path is:
* `collector` gathers normalized data
* `analyzer` builds analyses through module orchestration and ensemble review
* `decision` converts analyses into conviction-based actions
* `state` updates signal history and derived outcomes
* `output` writes Markdown and JSON payloads
* `datastore` persists run metadata and historical records
* `logging` records execution and derives operational reports

## Boundary Rules

* Never bypass datastore for persistence
* Never move business rules into GitHub Actions or Vercel build scripts
* Never let output formatting become the source of truth for analysis logic
* Never let analyzer perform direct provider fetching
* Keep optional features additive and non-destructive
