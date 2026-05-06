# Pipeline Runtime Speed Controls Design

## Status

Approved for planning on 2026-05-06.

## Context

The latest full pipeline run finished successfully, but it took about 30 minutes. Log inspection showed the main watchlist analysis completed before the final sector scan work, while the tail of the run spent several minutes collecting sector-explorer news and refreshing `sectors.json`.

Observed runtime signals from `logs/pipeline/2026-05-04.jsonl`:

- Total logged duration: about 30.1 minutes.
- OpenAI calls: 185.
- LLM usage: about 696,912 total tokens.
- Policy analyzer: about 136 seconds.
- Sector scan tail: multiple long news-collection gaps after the primary watchlist outputs were already written.
- Obsidian sync: 24 permission warnings, noisy but not a source-of-truth output failure.

The goal is not to reduce research quality. The accepted direction is to preserve the watchlist analysis, decision, state, Markdown, JSON, and web output quality while removing sector scan latency from the default `python main.py` completion path.

## Goals

- Make default `python main.py` finish after the watchlist pipeline and web-facing watchlist outputs are complete.
- Keep sector explorer quality intact by preserving the existing sector scan implementation.
- Add an explicit `--with-sectors` flag for full runs that include sector scanning.
- Keep existing sector artifacts when sector scan is skipped; do not delete or blank `output/data/sectors.json`.
- Log the skip clearly so operators understand why sectors were not refreshed.
- Keep the pipeline invariant intact: `collect -> analyze -> state -> output -> store -> log`.

## Non-Goals

- No reduction in LLM analysis quality for watchlist tickers.
- No change to official `buy` / `watch` / `avoid` decision logic.
- No change to sector scan ranking or sector collector behavior.
- No new real-time system, scheduler, or external dependency.
- No UI redesign for stale sector data in this phase.

## Accepted Approach

The accepted approach is an option-gated sector scan:

- `python main.py` runs the primary watchlist pipeline only.
- `python main.py --with-sectors` runs the primary watchlist pipeline and then refreshes the sector explorer payload.
- Existing standalone sector execution remains available if already supported by the repo, such as `python -m src.cli.run_sectors`.

This is intentionally small. It changes runtime routing and documentation, not analysis semantics.

## Runtime Behavior

### Default Run

Command:

```powershell
python main.py
```

Expected scope:

```text
load config
-> collect watchlist data
-> analyze watchlist
-> refresh state and signal statistics
-> generate decisions
-> write Markdown and JSON outputs
-> sync selected web/public and web/dist payloads
-> log sector_scan_skipped
-> finalize pipeline summary
```

The default run does not call the sector scan function. Existing sector output remains untouched.

### Full Run

Command:

```powershell
python main.py --with-sectors
```

Expected scope:

```text
default run scope
-> run sector scan
-> refresh output/data/sectors.json
-> sync selected sector/web payloads
-> log sector_scan_completed
-> finalize pipeline summary
```

The full run preserves current behavior for operators who want all artifacts refreshed in one command.

### Collector-Only Run

Command:

```powershell
python main.py --collect-only
```

Expected scope remains unchanged. This mode is still for intraday refresh and should not trigger sector scanning.

## CLI Contract

`main.py` should expose a new boolean flag:

```text
--with-sectors
```

Help text should make the default clear:

```text
Run sector explorer refresh after the main watchlist pipeline.
Skipped by default to keep normal runs fast.
```

If both `--collect-only` and `--with-sectors` are passed, `--collect-only` should win because it is a separate intraday refresh mode. The CLI should not run sector scanning in collect-only mode.

## Pipeline API Contract

`src.pipeline.run_pipeline()` should accept a keyword-only boolean, for example:

```python
run_pipeline(with_sectors: bool = False)
```

The default must be `False` so tests, local usage, and scheduled runs become faster unless they explicitly request sector refresh.

When `with_sectors` is `False`, the pipeline should emit a skip event after the main outputs are complete:

```json
{
  "component": "pipeline",
  "event": "sector_scan_skipped",
  "reason": "disabled_by_default",
  "hint": "run with --with-sectors to refresh sectors.json"
}
```

When `with_sectors` is `True`, the current sector scan path runs and logs `sector_scan_completed` as it does today.

## Output Policy

`output/data` remains the source of truth.

Default runs:

- Update watchlist-facing artifacts such as `index.json`, ticker shards, `dashboard_history.json`, Markdown reports, API status, quality reports, cost logs, and web mirrors.
- Do not rewrite `output/data/sectors.json`.
- Do not delete `web/public/output/data/sectors.json` or `web/dist/output/data/sectors.json`.

Full runs:

- Update all default-run outputs.
- Refresh `output/data/sectors.json`.
- Sync `sectors.json` to web mirrors using the existing output sync path.

This preserves frontend behavior: sector pages can continue showing the most recent successful sector scan while the main dashboard reflects the latest watchlist run.

## Logging And Observability

The pipeline summary should continue to report success when the default run skips sector scanning intentionally.

Required events:

- `sector_scan_skipped` on default runs.
- `sector_scan_completed` on full runs.

Optional future telemetry, outside this phase:

- `sector_data_age_hours`.
- `sector_scan_duration_seconds`.
- `sector_scan_last_success_date`.

These are intentionally deferred to keep this phase focused.

## Documentation Updates

Update:

- `docs/pipeline-runtime.md`: document default and full run scopes.
- `docs/output.md`: clarify that `sectors.json` is refreshed by sector scan runs and preserved on default runs.
- CLI help: expose `--with-sectors`.

No schema version bump is required because this design does not change web payload shape.

## Tests

Add or update focused tests for:

- `run_pipeline()` default path does not call sector scan.
- `run_pipeline(with_sectors=True)` calls sector scan.
- Default path records `sector_scan_skipped`.
- `--with-sectors` is wired from `main.py` to `run_pipeline(with_sectors=True)`.
- `--collect-only` does not trigger sector scan even if `--with-sectors` is also passed.

Retain existing output and pipeline tests. Run at least:

```powershell
python -m compileall main.py src tests
python -m pytest tests/test_pipeline.py tests/test_pipeline_quality_wiring.py -q
```

When practical, also run:

```powershell
cd web
npm run build
npm run lint
```

## Risks And Mitigations

Risk: Operators may expect `python main.py` to refresh sectors.

Mitigation: Add clear CLI help, runtime skip logging, and documentation.

Risk: Sector page may show older data than the main dashboard.

Mitigation: Preserve existing sector payload instead of deleting it, and make full refresh available through `--with-sectors`.

Risk: Tests assume sector scan always runs.

Mitigation: Update tests to assert the new default explicitly and add coverage for the full-run flag.

Risk: GitHub Actions or local scripts depend on old behavior.

Mitigation: Document the new command split. Existing schedules that need full refresh should call `python main.py --with-sectors`.

## Expected Impact

The expected first-order runtime improvement is removing the sector scan tail from default runs. Based on the observed 2026-05-04 run, this should save roughly 7 to 10 minutes on normal local runs without reducing watchlist analysis quality.

This does not address the 185 LLM calls or committee retry volume. Those are quality-affecting optimization candidates and should be handled in a separate design if needed.

## Implementation Boundary

The implementation should be limited to:

- `main.py` CLI flag parsing.
- `src/pipeline.py` runtime routing.
- Focused tests for the new routing behavior.
- Related docs.

No analyzer, decision, collector ranking, or frontend UI behavior should be changed in this phase.
