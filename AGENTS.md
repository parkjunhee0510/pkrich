# AGENTS.md

Navigation index for agents. Detailed knowledge lives in `docs/`, not here.

## Agent Entrypoints

- Codex: read `docs/codex/index.md` after this file. Use it as the only Codex routing hub before opening layer docs.
- Claude: use `CLAUDE.md`.

## System

Batch stock research automation. Daily GitHub Actions run -> structured data -> LLM analysis -> Markdown/JSON output. Cost-constrained (< $5/month).

## Pipeline Invariant

`collect -> analyze -> state -> output -> store -> log`; see `docs/pipeline.md`.

## Layers

| Layer | Role | Primary Docs |
|-------|------|--------------|
| collector | External data collection with approved sources and fallback chains | `docs/data-collection.md` |
| analyzer | LLM prompt, provider, parsing, validation, structured output, and cost-aware batching | `docs/analyzer.md`, `docs/cost.md` |
| decision | Factor scoring and conviction logic | `docs/decision.md`, `docs/architecture.md` |
| state | Portfolio and signal state with reproducible, dependency-light behavior | `docs/state.md` |
| output | Deterministic Markdown, JSON, CSV, and user-facing artifact formatting | `docs/output.md` |
| datastore | Persistence abstraction; all storage goes through this layer | `docs/datastore.md` |
| logging | Pipeline event tracking and runtime observability | `docs/logging.md` |
| utils | Shared helpers such as macro sensitivity, beta, event matching, and model config | `docs/utils.md`, `docs/architecture.md` |

## Workflow

1. Read this file first.
2. If you are Codex, read `docs/codex/index.md` next and follow its routing rules.
3. Open only the matching layer docs for the current task.
4. Apply any nested `AGENTS.md` file whose scope contains files you touch.
5. Open source files only after the relevant docs are known.
6. When code changes behavior, contracts, routing, or outputs, update the relevant docs in the same task.

## Boundary Rules

- Keep this file as a compact navigation index.
- Keep Codex task routing in `docs/codex/index.md`.
- Keep layer-specific contracts in layer docs or scoped `AGENTS.md` files.
- Do not read all docs blindly or break layer boundaries.

## Non-Goals

No real-time systems, no trading automation, no complex infra.

## Done When

Pipeline runs end-to-end, outputs are valid, architecture is preserved, related docs are updated, and cost remains unchanged.
