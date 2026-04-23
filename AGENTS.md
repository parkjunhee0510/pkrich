# AGENTS.md

Navigation index for agents. Detailed knowledge lives in `docs/`, not here.

## Agent entrypoints

- Codex: read `docs/codex/index.md` after this file. Use it as the only navigation hub before opening layer docs.
- Claude: use `CLAUDE.md`.

## System

Batch stock research automation. Daily GitHub Actions run → structured data → LLM analysis → Markdown/JSON output. Cost-constrained (< $5/month).

## Pipeline (invariant)

`collect → analyze → state → output → store → log` — see `docs/pipeline.md`.

## Layers & constraints

| Layer | Role | Constraints | Docs |
|-------|------|-------------|------|
| collector | External data | Approved sources, fallback chains | `docs/data-collection.md` |
| analyzer  | LLM logic | Deterministic prompts, structured output, minimize/batch calls | `docs/analyzer.md`, `docs/cost.md` |
| decision  | Factor scoring & conviction | — | `docs/decision.md`, `docs/architecture.md` |
| state     | Portfolio & signals | Reproducible, no external deps | `docs/state.md` |
| output    | Formatting | Deterministic, minimal diffs | `docs/output.md` |
| datastore | Persistence abstraction | All storage goes through it | `docs/datastore.md` |
| logging   | Pipeline tracking | Record all pipeline events | `docs/logging.md` |
| utils     | Shared helpers (macro sensitivity/beta, event matching, model config) | — | `docs/utils.md`, `docs/architecture.md` |

## Workflow

1. Read AGENTS.md.
2. If you are Codex, read `docs/codex/index.md` next and follow its routing rules.
3. Open only the matching layer docs for the current task.
4. Never read all docs blindly or break layer boundaries.
5. When code changes behavior, contracts, routing, or outputs, update the relevant docs in the same task.

## Non-goals

No real-time systems, no trading automation, no complex infra.

## Done when

Pipeline runs end-to-end, outputs valid, architecture preserved, related docs are updated, cost unchanged.
