# Codex Index

Codex uses this file as its only routing hub after `AGENTS.md`.

## Goal

Load the smallest useful context for the current task.

## Required Flow

1. Read root `AGENTS.md`.
2. Read this file.
3. Identify the task type and primary layer.
4. Open only the linked docs for that layer or task.
5. Apply any nested `AGENTS.md` file whose scope contains files you touch.
6. Open source files on `collect -> analyze -> state -> output -> store -> log`
ly after the relevant docs are known.

## Default Rules

- Do not read `CLAUDE.md` by default.
- Do not scan all files in `docs/`.
- Do not mix multiple layer docs unless the task clearly crosses boundaries.
- Prefer `docs/pipeline.md` only for end-to-end pipeline changes or uncertainty about stage order.
- Prefer the smallest doc set that can answer the current task.
- If code changes behavior, contracts, routing, or outputs, update the matching docs before finishing.

## Scoped Instruction Files

When editing files inside a directory that contains a nested `AGENTS.md`, follow that nested file after this routing file.

Known source-scope instruction files:

- `src/analyzer/AGENTS.md`
- `src/output/AGENTS.md`

Known artifact-scope instruction files:

- `output/AGENTS.md`

## Task Routing

### Collector Work

Read:

- `docs/data-collection.md`
- `docs/pipeline.md` only if the change affects collect-stage inputs or handoff

Then inspect:

- `src/collector/`
- related config under `config/`

### Analyzer Work

Read:

- `docs/analyzer.md`
- `docs/cost.md`
- `docs/pipeline.md` only if prompt inputs, outputs, or batching flow changes

Then inspect:

- `src/analyzer/`
- `config/models.yaml`

### Decision Or Shared Utils Work

Read:

- `docs/architecture.md`
- `docs/decision.md` for decision logic
- `docs/utils.md` for shared helpers
- `docs/state.md` if portfolio or signal state is involved

Then inspect:

- `src/decision/`
- `src/utils/`

### State Or Datastore Work

Read:

- `docs/state.md`
- `docs/datastore.md`
- `docs/pipeline-boundaries.md` only if stage boundaries or persistence timing changes

Then inspect:

- `src/utils/datastore.py`
- `src/utils/signal_tracker.py`
- other touched persistence files

### Output Or Frontend Data Work

Read:

- `docs/output.md`
- `docs/datastore.md` only if exported data shape depends on storage

Then inspect:

- `src/output/`
- `output/data/` samples if generated data shape or artifact content matters
- `web/src/` only for read-only frontend consumption changes

### Logging Or Observability Work

Read:

- `docs/logging.md`
- `docs/pipeline-runtime.md` only if event timing across stages matters

Then inspect:

- `src/utils/pipeline_logging.py`
- call sites that emit pipeline events

### Testing Or Verification Work

Read:

- `docs/testing.md`
- the layer doc for the code under test

Then inspect:

- `tests/`
- touched implementation files

## Escalation Cases

Open additional docs only when at least one of these is true:

- the task spans multiple layers
- the current doc points to another doc as required context
- an end-to-end invariant is unclear without a pipeline doc
- output, storage, and logging contracts all change together

## Avoid These Files Unless Directly Relevant

- `CLAUDE.md`
- roadmap or review docs
- UI planning docs for backend-only work
- historical notes that do not define current behavior

See `docs/codex/non-operational.md` for the default skip list.

## Done Check

Before finishing, confirm:

- only relevant docs were loaded
- layer boundaries were preserved
- any changed behavior, contracts, outputs, or routing rules were reflected in related docs
- changes still respect