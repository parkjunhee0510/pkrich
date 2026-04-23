# Pipeline

## Codex Routing

- Read first only when the task is pipeline-wide and you need to choose between runtime flow and boundary rules.
- For execution order and stage responsibilities, go to `docs/pipeline-runtime.md`.
- For handoff contracts and cross-layer limits, go to `docs/pipeline-boundaries.md`.

## Overview

The system runs as a deterministic batch pipeline.

Core invariant:
collect -> analyze -> state -> output -> store -> log

Primary entrypoint:
* `src/pipeline.py::run_pipeline()`

Secondary entrypoint:
* `src/pipeline.py::collect_only()` for intraday price refresh without full analysis

## Document Map

- `docs/pipeline-runtime.md`: runtime stages, entrypoints, feature flags, and output phases
- `docs/pipeline-boundaries.md`: handoff contracts, layer limits, and pipeline-wide invariants

## Completion Criteria

A healthy run should:
* Complete end-to-end without breaking the invariant order
* Produce valid ticker analyses and decisions
* Update state and derived metrics
* Write deterministic Markdown and JSON outputs
* Record pipeline logs and operational summaries
