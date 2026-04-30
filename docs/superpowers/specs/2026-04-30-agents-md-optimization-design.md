# AGENTS.md Optimization Design

## Purpose

This design optimizes the agent instruction surface for maintainability. The goal is to keep each instruction file responsible for one clear job while preserving the current layered architecture and Codex routing flow.

The primary outcome is consistency across four instruction surfaces:

- Root `AGENTS.md`
- `docs/codex/index.md`
- Nested `AGENTS.md` files under scoped directories
- `.codex/agents/*.toml` role definitions

Human-facing explanatory notes may use concise Korean where helpful, but routing keywords, layer names, file paths, and role names stay in English for tool and agent compatibility.

## Current Context

The root `AGENTS.md` already acts as a short navigation index. It tells Codex to read `docs/codex/index.md`, names the pipeline invariant, lists layers, and defines completion expectations.

`docs/codex/index.md` already acts as the Codex-specific routing hub. It maps task types to layer docs and source areas, and it lists documents that should not be opened by default.

Nested `AGENTS.md` files currently exist for analyzer and output areas. They provide local boundary rules for those areas.

`.codex/agents/*.toml` defines role behavior for local agent roles such as planner, implementer, reviewer, tester, and code-mapper. Each role must include a non-empty `description`.

## Recommended Approach

Use a role-separated consistency cleanup.

The root `AGENTS.md` remains the top-level contract. It should describe the project, entrypoints, invariant pipeline, layer list, workflow, non-goals, and done criteria. It should not duplicate detailed Codex routing rules.

`docs/codex/index.md` remains the single Codex routing table. It should decide which docs to open for each task type, when to escalate to extra docs, and which documents are non-operational by default.

Nested `AGENTS.md` files remain local scope contracts. They should define only the responsibilities, non-responsibilities, and completion criteria for their scoped directories.

`.codex/agents/*.toml` remains role behavior configuration. It should not copy the full routing table. It should use the same layer names and direct agents to follow root `AGENTS.md` and `docs/codex/index.md` when relevant.

This approach preserves the existing structure and reduces drift without moving knowledge into a single oversized document.

## Document Boundaries

### Root `AGENTS.md`

Root `AGENTS.md` is the first instruction surface for all agents. It should stay short and durable.

It should contain:

- Agent entrypoints
- One-paragraph system summary
- ASCII pipeline invariant: `collect -> analyze -> state -> output -> store -> log`
- Layer table with stable layer names
- High-level workflow
- Non-goals
- Done criteria

It should avoid:

- Detailed Codex task routing
- Layer-specific implementation rules
- Historical notes
- Long examples
- Duplicated content from nested `AGENTS.md`

### `docs/codex/index.md`

`docs/codex/index.md` is the only Codex routing hub after root `AGENTS.md`.

It should contain:

- Required read order
- Default context-loading rules
- Task-to-doc routing
- Source directories to inspect after docs
- Escalation rules for cross-layer tasks
- Non-operational docs guidance
- Codex done check

It should avoid:

- Repeating the full root layer table
- Repeating local analyzer or output rules
- Explaining non-Codex agent behavior
- Broad project history

### Nested `AGENTS.md`

Nested `AGENTS.md` files are scoped contracts. The current scoped files are:

- `analyzer/AGENTS.md`
- `output/AGENTS.md`

They should contain:

- Scope
- Layer responsibilities
- Explicit non-responsibilities
- Local design rules
- Local completion criteria

They should avoid:

- Repeating root workflow rules
- Repeating Codex task routing
- Describing unrelated layers
- Changing pipeline order

### `.codex/agents/*.toml`

Agent role TOML files define behavior, not architecture.

They should contain:

- `name`
- `description`
- role-specific reasoning or sandbox settings
- concise `developer_instructions`
- consistent return expectations where the role returns findings or validation summaries

They should avoid:

- Copying the full layer routing table
- Embedding stale docs lists
- Contradicting root `AGENTS.md`
- Using different layer names from the docs

## Terminology Rules

Use these layer names consistently:

- `collector`
- `analyzer`
- `decision`
- `state`
- `output`
- `datastore`
- `logging`
- `utils`

Use ASCII arrows in durable agent instructions:

```text
collect -> analyze -> state -> output -> store -> log
```

Avoid non-ASCII arrows in routing-critical text because past output has shown mojibake such as `??` in place of arrows.

Use English for:

- file paths
- role names
- layer names
- routing labels
- test and validation command names

Use Korean only as short explanatory support where it improves human readability and does not define machine-critical routing.

## File-Level Change Plan

### Root `AGENTS.md`

Keep the current structure and tighten wording.

Planned edits:

- Replace broken arrow text with ASCII arrows.
- Keep Codex and Claude entrypoints.
- Keep the layer table, but remove ambiguous blank constraint cells.
- Ensure the root workflow points Codex to `docs/codex/index.md` without duplicating routing details.
- Keep done criteria aligned with the pipeline and docs update rule.

### `docs/codex/index.md`

Keep the current routing structure and align terminology.

Planned edits:

- Replace broken arrow text with ASCII arrows.
- Add a brief reminder that nested `AGENTS.md` files apply when editing scoped directories.
- Keep task routing in this file only.
- Ensure done check mirrors root completion terms without duplicating the full root contract.

### `analyzer/AGENTS.md`

Keep the existing local analyzer rules.

Planned edits:

- Preserve analyzer boundaries around LLM input, prompt construction, provider calls, parsing, validation, and normalized analysis output.
- Remove or reduce formatting noise only if it improves readability.
- Avoid changing analyzer behavior rules unless they conflict with root or Codex index terminology.

### `output/AGENTS.md`

Keep the existing local output rules.

Planned edits:

- Replace mojibake in directory tree examples and title examples with ASCII text.
- Preserve deterministic Markdown, JSON/CSV output, and Obsidian compatibility rules.
- Ensure output remains presentation-focused and does not claim analyzer or collector responsibility.

### `.codex/agents/*.toml`

Normalize role metadata and wording if writable.

Planned edits:

- Verify every role has a non-empty `description`.
- Keep role descriptions concise and action-oriented.
- Align role instructions with the same root and Codex index read order.
- Keep planner read-only.
- Keep reviewer read-only.
- Keep tester focused on validation.
- Keep implementer focused on minimal scoped changes.
- Keep code-mapper focused on read-only codebase mapping.

If the sandbox cannot write `.codex/agents/*.toml`, implementation should stop short of forced permission changes and report exact manual edits instead.

## Validation Plan

Run a TOML validation check for `.codex/agents/*.toml`:

- Each file parses with `tomllib`.
- Each file has a non-empty `description`.
- No role file has malformed top-level syntax.

Run text checks for instruction drift:

- Search touched instruction files for mojibake such as `??`.
- Search touched instruction files for obsolete references such as `docs/pipline.md`.
- Confirm root `AGENTS.md` does not duplicate Codex task routing.
- Confirm `docs/codex/index.md` remains the routing hub.
- Confirm nested `AGENTS.md` files describe only their scoped layer.

Review the final diff manually:

- The root file stays compact.
- Routing details stay in `docs/codex/index.md`.
- Layer names match across touched files.
- Pipeline order remains `collect -> analyze -> state -> output -> store -> log`.

## Completion Criteria

The optimization is complete when:

- Root `AGENTS.md` remains a short navigation index.
- `docs/codex/index.md` remains the only Codex routing hub.
- Nested `AGENTS.md` files remain local layer contracts.
- `.codex/agents/*.toml` role descriptions are present and consistent, or blocked edits are documented.
- Durable routing text uses ASCII-safe syntax.
- No changed instruction file introduces layer-boundary drift.
- Validation commands and any blocked files are reported.

## Out Of Scope

This design does not change pipeline behavior.

It does not redesign collector, analyzer, decision, state, output, datastore, logging, or utils code.

It does not merge all docs into one instruction file.

It does not rewrite historical planning, roadmap, or review docs.

It does not require changing permissions on `.codex` files unless the user explicitly asks for that operational fix.
