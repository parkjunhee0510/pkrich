# AGENTS.md

## Scope

This file applies to output source code under `src/output/`.

## Responsibility

The output layer renders already-processed information into deterministic Markdown, JSON, CSV, dashboard data, and optional Slack notifications.

## Not Responsible For

- Fetching external data
- Prompting the LLM
- Performing business analysis
- Cleaning raw scraped payloads
- Owning persistence outside the datastore abstraction

## Rules

- Keep rendering deterministic, readable, Obsidian-compatible, and diff-friendly.
- Preserve visible note structure, filenames, paths, and schema names unless a migration is explicitly requested.
- Keep heading order, section names, table column order, and CSV column order stable.
- Prefer plain Markdown headings, bullet lists, and tables.
- Avoid decorative formatting noise.
- Separate rendering logic from file I/O where practical.
- Keep Slack output optional and secondary; Slack failures must not break core artifact generation.
- Do not move analyzer, collector, decision, state, datastore, or logging responsibilities into output code.

## Standard Artifact Shape

Daily notes use stable sections such as title, market overview, watchlist summary, top movers, and action items.

Ticker notes use stable sections such as title, summary, key news, financial highlights, risks or watchpoints, and data snapshot.

Machine-readable outputs use fixed field names, fixed column order, explicit missing-value handling, and consistent date formatting.

## Completion Criteria

Output source changes are complete only when Markdown remains stable and readable, Obsidian compatibility is preserved, file paths and filenames remain consistent, schemas remain stable or documented, and optional outputs do not break core artifact generation.
