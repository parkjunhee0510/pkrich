# Codex Index

Codex uses this file as its only navigation hub after `AGENTS.md`.

## Goal

Load the smallest useful context for the current task.

## Required flow

1. Read `AGENTS.md`.
2. Read this file.
3. Identify the task type and the primary layer.
4. Open only the linked docs for that layer or task.
5. Open source files only after the relevant docs are known.

## Default rules

- Do not read `CLAUDE.md` by default.
- Do not scan all files in `docs/`.
- Do not mix multiple layer docs unless the task clearly crosses boundaries.
- Prefer `docs/pipeline.md` only for end-to-end pipeline changes or uncertainty about stage order.
- Prefer the smallest doc set that can answer the current task.
- If code changes behavior, update the matching layer docs before finishing.

## Task routing

### Collector work

Read:
- `docs/data-collection.md`
- `docs/pipeline.md` only if the change affects collect-stage inputs or handoff

Then inspect:
- `src/collector/`
- related config under `config/`

### Analyzer work

Read:
- `docs/analyzer.md`
- `docs/cost.md`
- `docs/pipeline.md` only if prompt inputs/outputs or batching flow changes

Then inspect:
- `src/analyzer/`
- `config/models.yaml`

### Decision or shared utils work

Read:
- `docs/architecture.md`
- `docs/decision.md` for decision logic
- `docs/utils.md` for shared helpers
- `docs/state.md` if portfolio or signal state is involved

Then inspect:
- `src/decision/`
- `src/utils/`

### State or datastore work

Read:
- `docs/state.md`
- `docs/datastore.md`
- `docs/pipeline-boundaries.md` only if stage boundaries or persistence timing changes

Then inspect:
- `src/utils/datastore.py`
- `src/utils/signal_tracker.py`
- other touched persistence files

### Output or frontend data work

Read:
- `docs/output.md`
- `docs/datastore.md` only if exported data shape depends on storage

Then inspect:
- `src/output/`
- `output/data/` samples if needed
- `web/src/` only for read-only frontend consumption changes

### Logging or observability work

Read:
- `docs/logging.md`
- `docs/pipeline-runtime.md` only if event timing across stages matters

Then inspect:
- `src/utils/pipeline_logging.py`
- call sites that emit pipeline events

### Testing or verification work

Read:
- `docs/testing.md`
- the layer doc for the code under test

Then inspect:
- `tests/`
- touched implementation files

## Escalation cases

Open additional docs only when at least one of these is true:

- the task spans multiple layers
- the current doc points to another doc as required context
- an end-to-end invariant is unclear without a pipeline doc
- output, storage, and logging contracts all change together

## Avoid these files unless directly relevant

- `CLAUDE.md`
- roadmap or review docs
- UI planning docs for backend-only work
- historical notes that do not define current behavior

See `docs/codex/non-operational.md` for the default skip list.

## Done check

Before finishing, confirm:

- only relevant docs were loaded
- layer boundaries were preserved
- any changed behavior, contracts, outputs, or routing rules were reflected in related docs
- changes still respect `collect → analyze → state → output → store → log`
