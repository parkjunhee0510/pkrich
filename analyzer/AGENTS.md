# AGENTS.md

## Scope

This file applies to all code under `src/analyzer/`.

The analyzer layer is responsible for:

* preparing structured input for the LLM
* building prompts
* calling the LLM provider
* parsing and validating responses
* returning normalized analysis objects to downstream output modules

It is NOT responsible for:

* fetching external data
* formatting final Markdown files
* writing files to disk
* sending Slack messages

---

## Core Responsibility Rules

* Analyzer code must accept normalized, structured input only
* Analyzer code must return structured, machine-friendly output
* Keep provider-specific logic isolated to this layer
* Do not leak raw provider response formats outside analyzer
* Do not embed file path or rendering logic in analyzer code

---

## Prompt Design Rules

Prompts must be:

* deterministic
* concise
* cost-aware
* reusable
* easy to diff and review

### Always separate prompt parts

Use a clear structure:

1. system instructions
2. task instructions
3. structured input data
4. output schema / formatting constraints

### Prefer explicit constraints

Prompts should explicitly specify:

* tone
* scope
* forbidden behaviors
* output fields
* max section sizes when needed

### Avoid vague requests

Do NOT use prompt wording like:

* "analyze freely"
* "be creative"
* "write a detailed report"
  unless explicitly requested.

### Prefer low-ambiguity instructions

Good prompt goals:

* summarize key developments
* identify notable risks
* extract material financial highlights
* produce structured fields for downstream rendering

---

## Prompt Template Policy

Prompt templates should be kept:

* centralized
* versionable
* easy to edit without touching unrelated business logic

If prompts become large or multiply:

* extract them into dedicated template constants or files
* keep variable interpolation explicit
* avoid hidden prompt assembly across many functions

---

## Token Efficiency Rules

This project is cost-constrained.

Therefore:

* avoid repeating instructions across batched items
* batch multiple tickers per request when practical
* pass only relevant fields to the model
* trim redundant headlines and duplicate content
* prefer concise schema-driven output over verbose prose

Do NOT:

* send entire raw payloads if summarized structured data is enough
* ask the model for stylistic flourishes that do not improve usefulness
* generate long narrative output by default

---

## Input Construction Rules

Analyzer inputs must be normalized before prompting.

Expected input characteristics:

* ticker metadata is already cleaned
* numeric values are pre-formatted or normalized consistently
* news items are deduplicated
* empty / missing fields are handled explicitly
* timestamps and dates use a consistent format

Do NOT:

* pass inconsistent field names
* mix raw scraped text and normalized data in arbitrary ways
* rely on the model to clean obviously messy data if code can do it first

---

## Output Contract Rules

Analyzer outputs must be structured and stable.

Preferred output shape:

* summary
* key_news
* financial_highlights
* risks_or_watchpoints
* signal_or_takeaway
* optional structured table fields

Requirements:

* field names must stay stable
* output should be easy to validate
* output must be renderable without additional interpretation
* missing fields should degrade gracefully

Prefer JSON-like structured output internally even if final presentation is Markdown elsewhere.

---

## Hallucination Reduction Rules

Prompts must explicitly restrict the model to supplied data.

Always instruct the model to:

* use only provided market/news/financial inputs
* avoid fabricating figures
* mark uncertainty when data is missing
* avoid investment advice language unless explicitly requested

Do NOT:

* imply access to real-time external browsing inside the prompt
* ask the model to infer unsupported facts
* let it invent reasons for price moves without evidence in input

---

## Batching Rules

Batching is preferred when it reduces cost without harming clarity.

When batching:

* keep per-ticker boundaries explicit
* ensure output remains separable by ticker
* avoid prompt structures that allow one ticker's context to bleed into another
* validate each ticker's output independently if possible

If a batch becomes too large:

* split deterministically
* preserve stable ordering

---

## Provider Isolation Rules

* Keep model names configurable
* Keep API client logic isolated
* Keep retry behavior explicit
* Keep timeout/error handling local and predictable

Do not spread provider-specific assumptions across the rest of the codebase.

Switching providers or models should require minimal analyzer-only edits.

---

## Parsing & Validation Rules

* Validate model output before returning it
* Fail clearly on malformed structured output
* Prefer schema validation where practical
* If output is partially valid, salvage safe fields when possible
* Never silently return malformed structures as if valid

If the model response cannot be trusted:

* return a controlled fallback structure
* include enough signal for graceful downstream degradation

---

## Refactoring Rules

When changing analyzer code:

* preserve prompt intent unless explicitly asked to change behavior
* preserve output schema unless a migration is requested
* reduce token usage where possible
* improve observability without leaking secrets

Do NOT:

* move analyzer responsibilities into collector or output layers
* tightly couple prompts to Markdown formatting
* optimize for elegance at the expense of debuggability

---

## Logging Rules

Logs may include:

* ticker symbols
* counts of headlines
* batch sizes
* retry events
* validation failures

Logs must NOT include:

* API keys
* full sensitive environment values
* unnecessarily large prompt bodies
* unnecessarily large model responses

Prefer concise debug logs over dumping full payloads.

---

## Completion Criteria

A change in `src/analyzer/` is complete only if:

* prompt construction remains deterministic
* output schema remains stable
* token usage is not unnecessarily increased
* malformed outputs are handled safely
* downstream output modules can consume results without special-case hacks
