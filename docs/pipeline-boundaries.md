# Pipeline Boundaries

## Codex Routing

- Read when the task changes handoff contracts, layer boundaries, normalization rules, or what each stage is allowed to do.
- Pair with `docs/pipeline-runtime.md` only if execution order also changes.
- Then inspect the boundary-touching stage modules and `src/pipeline.py`.

## Stage Rules

### Collect

* External APIs are allowed only here
* Fallback chains live here
* Outputs must be normalized before leaving this step

### Analyze

* No direct external data fetching
* LLM outputs must remain structured and deterministic
* Fallbacks must preserve downstream schema stability

### Decide

* No external data fetching
* No output formatting

### State

* State must be reproducible from stored inputs and prior outputs
* No external API dependency

### Output

* No data fetching
* No new analysis logic
* Keep payloads deterministic and diff-friendly

### Store

* All persistence must go through the datastore abstraction
* No direct backend access from analyzer, output, or decision code

### Log

* Logging must not change business behavior
* Logging failures should not take down the pipeline unless the primary run has already failed

## Cross-Layer Invariants

* Preserve `collect -> analyze -> state -> output -> store -> log`
* Never bypass datastore for persistence
* Never move business rules into GitHub Actions or Vercel build scripts
* Never let output formatting become the source of truth for analysis logic
* Never let analyzer perform direct provider fetching
* Keep optional features additive and non-destructive
