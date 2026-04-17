# AGENTS.md

## Scope

This file applies to all code under `src/output/`.

The output layer is responsible for:

* rendering structured analysis into Markdown
* writing stable file contents
* producing CSV/history outputs when needed
* sending optional Slack notifications

It is NOT responsible for:

* fetching external data
* prompting the LLM
* performing business analysis
* cleaning raw scraped payloads

---

## Core Output Principle

Output must be:

* deterministic
* readable
* Obsidian-compatible
* diff-friendly
* stable over time

This layer exists to present already-processed information, not reinterpret it.

---

## Directory and Path Rules

Directory structure must remain:

output/
├── daily/
├── tickers/
└── data/

Requirements:

* daily summaries go under `output/daily/`
* ticker notes go under `output/tickers/<TICKER>/`
* tabular history files go under `output/data/`

Do NOT:

* invent ad hoc output directories
* change file naming conventions without explicit request
* scatter output generation rules across unrelated modules

---

## Markdown Stability Rules

Markdown formatting must stay stable across runs.

Goals:

* predictable Git diffs
* readable Obsidian notes
* minimal formatting churn

Therefore:

* keep heading order fixed
* keep section names fixed unless explicitly changed
* keep table column order fixed
* avoid random spacing changes
* avoid stylistic rewrites that do not change meaning

Do NOT:

* reorder sections dynamically without clear need
* switch between bullets/tables/paragraphs inconsistently
* introduce decorative formatting noise

---

## Daily Note Format Rules

Daily notes should use a consistent top-level structure.

Preferred order:

1. Title
2. Market Overview
3. Watchlist Summary
4. Top Movers
5. Action Items

Example shape:

* `# Daily Research — YYYY-MM-DD`
* `## Market Overview`
* `## Watchlist Summary`
* `## Top Movers`
* `## Action Items`

If a section has no data:

* render a minimal fallback line
* do not omit the section unless explicitly requested

---

## Ticker Note Format Rules

Ticker-specific notes must remain easy to scan.

Preferred order:

1. Title
2. Summary
3. Key News
4. Financial Highlights
5. Risks / Watchpoints
6. Data Snapshot

Example title:

* `# AAPL — 2026-04-08`

Rules:

* use fixed section headings
* keep short sections actually short
* use bullet lists when scanning is better than prose
* use tables only for clearly tabular data

---

## Table Rules

Use Markdown tables only when they improve clarity.

Good uses:

* watchlist summary
* compact metric snapshots
* historical summaries

Requirements:

* fixed column order
* plain, readable headers
* no excessive column count
* no unstable formatting based on content length

If table rendering becomes awkward:

* prefer bullet lists over malformed tables

---

## Obsidian Compatibility Rules

Markdown must render cleanly in Obsidian.

Therefore:

* use standard Markdown headings
* use standard bullet lists
* use plain Markdown tables
* avoid unsupported or fragile syntax unless explicitly needed

Do NOT:

* depend on custom HTML for core readability
* depend on external styling
* generate noisy embedded metadata blocks unless explicitly requested

---

## File Writing Rules

* Output generation should be deterministic from the same input
* File content should not include timestamps unless part of the document meaning
* Avoid rewriting identical content unnecessarily if the implementation supports it
* Preserve newline style consistently
* Ensure parent directories exist before writing

Do NOT:

* mix formatting and filesystem side effects in overly large functions
* hide path construction logic in many places
* make writes harder to test than necessary

---

## Slack Output Rules

Slack notifications are optional and secondary.

Requirements:

* Slack failure must not break Markdown generation
* Slack messages should remain concise
* Slack content should summarize, not duplicate the entire note
* Core research artifacts remain Markdown and CSV, not Slack

---

## CSV / Data Output Rules

CSV outputs must be:

* stable
* append-safe where applicable
* easy to inspect manually

Requirements:

* fixed column names
* fixed column order
* explicit handling for missing values
* consistent date formatting

Do NOT:

* change schema casually
* mix presentation-only labels into machine-friendly history files

---

## Refactoring Rules

When changing output code:

* preserve visible note structure unless explicitly asked to redesign it
* preserve filenames and paths unless migration is requested
* favor readability over clever rendering abstractions
* separate rendering logic from file I/O where practical

Do NOT:

* move business analysis logic into output modules
* make Markdown rendering depend on provider-specific LLM quirks
* overabstract simple templates

---

## Validation Rules
    
Before considering output changes complete:

* verify rendered Markdown is readable as raw text
* verify rendered Markdown is readable in Obsidian
* verify section order is unchanged
* verify tables still render correctly
* verify paths and filenames remain correct
* verify Slack remains optional and non-blocking
* verify CSV schema remains stable

---

## Completion Criteria

A change in `src/output/` is complete only if:

* Markdown remains stable and readable
* Obsidian compatibility is preserved
* file paths and filenames remain consistent
* Git diffs stay clean for equivalent input
* optional outputs do not break core artifact generation
