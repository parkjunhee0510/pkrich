# Logging

## Codex Routing

- Read when the task changes pipeline events, run status reporting, or derived operational reports.
- Pair with `docs/pipeline.md` only if stage timing or event boundaries are affected.
- Then inspect `src/utils/pipeline_logging.py` and event call sites.

## Purpose

Track pipeline execution, failures, warnings, and derived operational metrics.

## Current Logging Model

### Event Stream

* Pipeline records structured step-level events during execution
* Events are used for diagnosis and for derived reports

### Run Finalization

* Each run is finalized with success or failure status
* Analysis-run metadata is recorded through datastore-backed paths

### Derived Operational Outputs

The logging pipeline currently feeds:
* API status reports
* analysis quality reports
* cost logs
* routing outcome summaries

## Requirements

* Record critical lifecycle events
* Keep secrets out of logs
* Preserve enough metadata for debugging without duplicating raw payloads excessively

## Rules

* Logging must not change pipeline control flow
* Logging failures should degrade gracefully where possible
* Derived reports are operational artifacts, not the source of truth for core business state
