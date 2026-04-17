# AGENTS.md

## Purpose

This file is the navigation index for agents.
Do not store detailed knowledge here.

---

## System Overview

Batch-based stock research automation system.

* Daily execution (GitHub Actions)
* Structured data → LLM analysis → Markdown/JSON output
* Cost-constrained (< $5/month)

---

## Pipeline (Invariant)

collect → analyze → state → output → store → log

See:

* docs/pipeline.md

---

## Architecture

Strict layered system:

* collector → external data
* analyzer → LLM logic
* state → portfolio & signals
* output → formatting
* datastore → persistence abstraction
* logging → pipeline tracking

See:

* docs/architecture.md

---

## Key Constraints

### Cost

* Minimize LLM usage
* Prefer batching

See:

* docs/cost.md

### Data Collection

* Use approved sources only
* Must implement fallback chains

See:

* docs/data-collection.md

### Analyzer

* Deterministic prompts
* Structured output only

See:

* docs/analyzer.md

### State

* Must be reproducible
* No external dependency

See:

* docs/state.md

### Output

* Deterministic
* Minimal diffs

See:

* docs/output.md

### Storage

* Must go through datastore abstraction

See:

* docs/datastore.md

### Logging

* Record all pipeline events

See:

* docs/logging.md

---

## Workflow for Agents

When solving tasks:

1. Read AGENTS.md
2. Identify relevant layer
3. Open corresponding docs/*
4. Execute within constraints

Never:

* Read entire docs blindly
* Break layer boundaries

---

## Non-Goals

* No real-time systems
* No trading automation
* No complex infrastructure

---

## Completion Criteria

* Pipeline runs end-to-end
* Outputs valid
* Architecture preserved
* Cost unchanged
