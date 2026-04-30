# AGENTS.md

## Scope

This file applies to analyzer source code under `src/analyzer/`.

## Responsibility

The analyzer layer prepares structured input for the LLM, builds deterministic prompts, calls the configured provider, parses and validates responses, and returns normalized analysis objects to downstream layers.

## Not Responsible For

- Fetching external data
- Formatting final Markdown
- Writing research artifacts to disk
- Sending Slack messages
- Storing pipeline state

## Rules

- Accept normalized, structured input only.
- Return structured, machine-friendly output.
- Keep provider-specific logic isolated in this layer.
- Do not leak raw provider response formats outside analyzer code.
- Keep prompts deterministic, concise, cost-aware, reusable, and easy to diff.
- Separate prompt parts into system instructions, task instructions, structured input data, and output schema constraints.
- Batch multiple tickers when it reduces cost without harming per-ticker separation.
- Validate model output before returning it.
- Return controlled fallback structures for malformed or incomplete model responses.
- Do not move collector, output, datastore, or logging responsibilities into analyzer code.

## Logging

Logs may include ticker symbols, headline counts, batch sizes, retry events, and validation failures.

Logs must not include API keys, full sensitive environment values, unnecessarily large prompt bodies, or unnecessarily large model responses.

## Completion Criteria

Analyzer changes are complete only when prompt construction remains deterministic, output schema remains stable or documented, token usage is not unnecessarily increased, malformed outputs are handled safely, and downstream output modules can consume results without special-case hacks.
