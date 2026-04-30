# AGENTS.md

## Scope

This file applies to generated research artifacts under `output/`.

Output source code lives under `src/output/`. Source-code instructions for rendering and export logic live in `src/output/AGENTS.md`.

## Artifact Rules

- Treat files under `output/` as generated artifacts unless the user explicitly asks for manual artifact edits.
- Keep generated Markdown, JSON, and CSV artifacts deterministic and diff-friendly.
- Preserve established directory names:

```text
output/
|-- cache/
|-- daily/
|-- tickers/
`-- data/
```

- Do not invent ad hoc output directories.
- Do not change artifact schemas or file naming conventions without a matching source-code and docs update.
- Do not move analyzer, collector, decision, state, datastore, or logging responsibilities into generated artifacts.

## Completion Criteria

Generated output changes are complete only when artifacts remain readable, stable, and consistent with the source output contracts in `src/output/AGENTS.md` and `docs/output.md`.
