---
name: output-artifact-audit
description: Use when checking generated stock output artifacts, output/data and web/public/output/data mirrors, ticker or sector shards, cost logs, routing outcomes, schema validation, stale files, or output health checks.
---

# Output Artifact Audit

Use this for generated-output cleanup and consistency tasks, especially after ticker, sector, cost, routing, or health-check changes.

## Workflow

1. Read `AGENTS.md`, `docs/codex/index.md`, and `docs/output.md`; read `docs/cost.md` only for cost or routing questions.
2. Apply `output/AGENTS.md` before touching generated artifacts under `output/`.
3. Verify source and web mirror consistency before editing:

```bash
python -m src.cli.output_health_check
```

4. Check `output/data` against `web/public/output/data` for missing, extra, or byte-mismatched mirrored JSON.
5. For ticker additions, verify watchlist/config placement, `output/data/tickers/<TICKER>`, dashboard/index references, price history, and markdown ticker output.
6. For sector additions, verify `config/sectors.yaml`, `output/data/sectors.json`, mirror parity, and exact ticker symbols.
7. For cost investigations, compare `cost_log.json`, `performance_baseline.json`, `routing_outcome.json`, and `search_evidence.json`.
8. Keep manual generated-artifact edits minimal and schema-compatible; prefer rerunning the pipeline or output CLI when feasible.

## Report

Return:

1. Problems found
2. What was fixed or intentionally left unchanged
3. Remaining risks, especially external fetch cost, stale upstream data, or docs not needing updates

## Guardrails

- Do not change output schema versions unless the contract truly changed.
- Do not change business logic while cleaning generated files.
- Do not perform external fetches without explicit user approval.
- Preserve `collect -> analyze -> state -> output -> store -> log`.
