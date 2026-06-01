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

### CLI Progress

* `python main.py` prints human-readable progress checkpoints to the CLI by default
* CLI progress is presentation-only and separate from the structured event stream
* `--no-progress` disables these messages for quiet automation runs
* Progress output failures must never change pipeline control flow or derived reports

### Run Finalization

* Each run is finalized with success or failure status
* Analysis-run metadata is recorded through datastore-backed paths
    
### Derived Operational Outputs

The logging pipeline currently feeds:
* API status reports
* analysis quality reports
* cost logs
* routing outcome summaries
* performance measurement summaries

BudgetGuard decisions are recorded as `budget_guard_decision` events. These events are informational in default shadow mode and are summarized in `output/data/cost_log.json`.

## Performance Measurement

Performance measurement consumes existing logs and output artifacts. It summarizes cost, LLM calls, validation quality, evidence coverage, signal quality, and JSON health.

Performance output failures should be logged or surfaced as output health issues. They must not change official recommendations. Invalid generated JSON remains a P0 operational issue because downstream reports and web mirrors must be parseable.

## Requirements

* Record critical lifecycle events
* Keep secrets out of logs
* Preserve enough metadata for debugging without duplicating raw payloads excessively

## Rules

* Logging must not change pipeline control flow
* Logging failures should degrade gracefully where possible
* Derived reports are operational artifacts, not the source of truth for core business state
