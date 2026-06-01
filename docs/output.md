# Output

## Codex Routing

- Read when the task changes exported markdown, JSON schema, frontend payloads, or output stability rules.
- Pair with `docs/datastore.md` only if output depends on stored shape or backfilled history.
- Then inspect `src/output/` and `web/src/` only when the frontend consumes changed data.

## Scope

The output layer turns finalized pipeline results into stable artifacts.

## Current Output Families

### Markdown

* daily note
* weekly note and structured weekly summary rendering
* per-ticker notes

### JSON For Web And Analytics

* `output/data/index.json`
* `output/data/tickers/<TICKER>/latest.json`
* `output/data/tickers/<TICKER>/history.json`
* `output/data/search_evidence.json`
* `output/data/search_audit.json`
* `output/data/backtest_summary.json`
* `output/data/monthly_summary.json`
* `output/data/routing_outcome.json`
* `output/data/signal_quality.json`
* `output/data/risk_intel_graph.json`
* `output/data/risk_intel_summary.json`
* `output/data/risk_intel_refresh_log.json`
* dashboard history, price history, ticker timelines
* sector explorer payloads

`routing_outcome.json` summarizes ensemble deep-review routing outcomes from persisted routing logs and evaluated signal rows. Its latest-run snapshot preserves router priority scores, router reason codes, priority skips, selected tickers, and deep-review cost estimates when those fields are present in `routing_log.json`; these fields are diagnostics only and must not change official decisions. The Backtest web page may render this latest-run router metadata as read-only routing diagnostics.

Per-ticker payloads now include:
* `factor_reasoning` surfaced from `decision/decision_layer.py` and `types.py`, written by `json_export.py`
* `ticker_macro_sensitivity` computed for all collected tickers, not portfolio-only
* `committee_analysis` for always-visible committee debate summaries plus PM conclusions
* the web dashboard and ticker detail UI consume `committee_analysis` as a presentation-layer debate record, separate from the official `decision`
* `decision.confidence_meta.search_evidence_score` and `decision.confidence_meta.search_quality_gate` when search evidence quality metadata is available; output serializes these fields without recomputing the score. The gate includes collector status fields such as `evidence_status`, `provider_status`, and `priority_for_refresh`.
* the web dashboard, action-change feed, today decision strip, and ticker detail UI may render search evidence metadata as badges or panels; these presentation cues must not mutate or reinterpret official decisions
* `pm_view` on the latest index payload and each `dashboard_history.days[]` entry for additive PM review context on held names
* `key_news_source_titles` and `key_news_reference_indices` alongside `key_news`, so short translated summaries remain display-friendly while citation audits can trace each item to its source headline

Dashboard payloads include `state_metadata` when available. This metadata records the state timing used by the decision and output layers, including whether decision-time signal statistics included the current run.

`news_references[*].published_at` is serialized as ISO date (`YYYY-MM-DD`) when the source provides an ISO or RFC822 timestamp.

`pm_view` is a review-oriented payload for the web UI. It is additive and must not override the official rule-based `buy` / `watch` / `avoid` decision.

Current `pm_view` fields:
* `as_of`
* `swap_candidates[]` with `held_ticker`, `candidate_ticker`, `swap_candidate_score`, `summary`, `reasons`, `overlap_context`, `review_points`
* `event_exposure_items[]` with `ticker`, `event_risk_score`, `event_label`, `event_date`, `days_until`, `summary`, `reasons`, `review_points`
* `today_priority_queue[]` with `priority_type`, `ticker`, `related_ticker`, `today_priority_score`, `summary`, `reasons`, `destination`
* `empty_states` for empty-safe frontend rendering

### Operational Reports

* API status
* analysis quality
* cost log
* routing outcome
* signal quality
* analysis performance under `output/data/analysis_performance.json`
* performance baseline and trends
* quality reliability loop under `output/data/quality_reliability_loop.json`
* A/B test results
* LLM audit reports under `docs/reports/llm-audit-YYYY-MM-DD.md` and `output/data/llm_audit/`
* LLM evidence manifests under `output/data/llm_evidence/<DATE>.jsonl`

`analysis_quality.json` includes the shared `schema_version`, `runs[]`, and `latest`. Each run row records the run date, success flag, daily API cost, analyzer batch and validation counts, warning counts, and a bounded `hallucination_ratio`. When a `web/` app exists beside `output/`, the writer also syncs this file to `web/public/output/data/analysis_quality.json` so the static dashboard reads the same operational payload as the pipeline output.

`cost_log.json` includes the shared `schema_version`, `runs[]`, and `latest`. Each run row records total estimated cost, model profile cost/token/call/model counts, ensemble routing counts, BudgetGuard summary counts and guarded path outcomes, and a deep-pass value summary. It is telemetry only and is not a billing ledger or decision input.

`validation_warnings.json` is also mirrored to `web/public/output/data/validation_warnings.json` because the admin surface reads it directly. The payload includes the shared `schema_version`, a `window_days` lookback, `generated_at`, `categories[]`, category `totals`, and chronological `series[]` rows with analyzer validation and warning counts. Sector explorer payloads are mirrored whenever the pipeline writes `sectors.json`, including the full pipeline sector-scan path.

`signal_quality.json` includes the shared `schema_version` and four read-only signal health panels: `ic_decay`, `rolling_ic`, `kelly`, and `turnover`. Writer fallback may emit `schema_version` plus a string `error` when signal-quality generation fails gracefully. The Admin and performance-measurement surfaces consume this artifact as observational telemetry only; they must not recompute official decisions or factor weights from it.

`api_status.json` is written for the requested calendar run date. This is intentionally distinct from the effective market date detected from price history, because API freshness and scheduled run status are calendar-run concerns. The summary records provider status/counts and LLM usage, cost, model counts, and optional analysis quality telemetry. `api_ticker_matrix.json` records one row per watchlist ticker with provider state values for the API status page.

LLM audit JSON reports include check dimensions, threshold metadata, sample counts, severity counts including `info`, and replay cost when D1 replay is enabled. Markdown reports include an executive summary, verdict matrix, per-check details, and methodology notes.

LLM evidence manifests are operational JSONL artifacts used by the eval audit layer. They contain stable hashes and call metadata only, not raw prompts or model responses. They are not copied into `web/public/output/data/` by default.

### Performance Measurement Outputs

The output layer writes performance measurement artifacts after cost, quality, routing, and evidence outputs are available.

* `output/data/performance_baseline.json`: latest run-level performance baseline, including JSON health, cost, quality, evidence, signal summaries, and a read-only `p1_readiness` block for future expansion review. Its cost summary records total and estimated monthly cost, budget usage, LLM calls, calls per ticker, routing counts, and BudgetGuard counts. Its quality summary records validation and warning counts plus bounded validation and hallucination ratios. Its signal summary records turnover and Kelly status. Its evidence summary records provider name, ticker and search counts, bounded coverage/freshness/cache/priority ratios, cache hit/stale-cache reuse, cache age, provider candidate counts, and status count maps when `search_evidence.json` provides priority and cache metadata. `performance_baseline.json.evidence` also derives `priority_refresh_candidate_count`, `priority_provider_error_count`, `priority_not_refreshed_count`, `priority_no_evidence_count`, and `priority_refresh_reasons` from the normalized search evidence metadata. Its `p1_readiness` block reports Search evidence provider, BudgetGuard, analysis performance, and output schema readiness without changing decisions, routing, or generated artifacts. The Search evidence provider track preserves provider call/error/cache-error/skipped counts, cap review status, priority candidate ratio, provider issue status, operational issue count, and stale-cache reuse status so live provider validation can be reviewed while the committed OpenAI mode remains capped, rate-limited, and provider-gated. The BudgetGuard readiness track preserves decision counts, guarded-path status counts, would-block/blocked/allow path counts, estimated incremental guarded cost, and an `enforce_review_status` so report-mode evidence can be reviewed before any explicit enforce-mode decision. The analysis performance readiness track preserves loop readiness, completed return-window count, evaluated signal-window count, conviction bucket coverage, regime/factor counts, factor attribution status, missing factor samples, and action-change coverage so quality-loop candidates can be reviewed without automatically changing official decisions or factor weights.
  When source telemetry is absent, the writer emits a normalized `status: "insufficient_data"` baseline, leaves `latest_run_date` empty, and uses explicit `insufficient_data` readiness details so health checks can distinguish sparse telemetry from malformed output.
* `output/data/performance_trends.json`: chronological run-by-run performance trend rows built from existing logs and generated artifacts. Each row includes run date, success flag, total cost, LLM calls, hallucination ratio, validation failure count, deep-selected count, and BudgetGuard would-block count.
* `output/data/quality_reliability_loop.json`: canonical V1 quality loop artifact. It combines decision-quality readiness, artifact reliability, evidence quality, and cost/runtime telemetry into one read-only payload. Cost is report-only in this loop and does not block quality telemetry. `quality_reliability_loop.json.warnings` may include `priority_evidence_not_refreshed`, `priority_evidence_provider_error`, `priority_evidence_zero_coverage`, and `priority_evidence_stale_cache` as operational diagnostics only. The artifact is observational and must not change official decisions, model routing, factor weights, or frontend behavior.
* `docs/reports/performance-YYYY-MM-DD.md`: human-readable performance summary for the run date.

These artifacts are observational. They do not change official decisions, model routing, or factor weights.

Use `python -m src.cli.write_performance_outputs --project-root .` to regenerate these artifacts from existing generated outputs without rerunning collection, analysis, or decision logic.

### Analysis Performance Outputs

`analysis_performance.json` is a shadow analytics artifact. It includes the shared `schema_version`, `as_of`, `summary`, `signal_performance`, `conviction_calibration`, `regime_performance`, `factor_attribution`, `action_change_reasons`, and additive `ai_recommendation_backtest`. It summarizes signal performance, conviction calibration, regime performance, factor attribution, ticker action-change reasons, and AI recommendation backtest telemetry from finalized decisions and persisted signal rows. In v1, `ai_recommendation_backtest` uses `basis: "final_action"` and evaluates finalized `buy` / `watch` / `avoid` actions against 1d, 5d, and 20d realized returns, high-conviction buckets, a ticker leaderboard, and best/worst examples. `watch` rows keep win and loss rates null, but their raw realized returns are still included in action summaries, ticker completed counts, ticker average returns, and notable examples; ticker win rates remain directional for `buy` and `avoid` recommendations. It must remain read-only shadow telemetry and must not recompute, override, or feed back into official decisions, model routing, factor weights, or execution behavior; factor attribution is reported as observed association rather than causal proof.

For legacy signal trackers created before decision metadata was persisted, `python -m src.cli.backfill_signal_metadata` can fill empty signal metadata fields from finalized `dashboard_history.json` and `index.json` snapshots before regenerating `analysis_performance.json`. This is a metadata migration only; it does not change official decisions.

The Backtest web page may render `analysis_performance.json` as read-only shadow telemetry alongside historical performance. The frontend must display the finalized payload as-is and must not recompute performance, change thresholds, or reinterpret official `buy` / `watch` / `avoid` decisions.

### Risk Intelligence Graph Outputs

Risk intelligence Phase 1.5 uses `output/data/risk_intel.sqlite` as the internal canonical store and writes three deterministic JSON artifacts after search evidence output is available. The SQLite store keeps graph runs, nodes, edges, evidence records, domain rules, input status, alert paths, health warnings, duplicate candidates, refresh patch lifecycle rows, and export manifests. The frontend and static web mirror continue to consume JSON only; `risk_intel.sqlite`, `risk_intel.sqlite-wal`, and `risk_intel.sqlite-shm` are never mirrored to `web/public/output/data/`.

* `output/data/risk_intel_graph.json`: canonical public JSON graph contract with `schema_version: "1.0.0"`, shared `generation.run_id`, Korean labels/summaries, `nodes`, `edges`, `source_records`, `domain_rules`, `input_status`, `health_warnings`, and explainable `alert_paths`.
* `output/data/risk_intel_summary.json`: dashboard-facing cards derived from the graph run. Cards include Korean `title_ko`, `summary_ko`, `alert_level_label_ko`, and ticker exposure details that distinguish `보유 종목` from `관심 종목`.
* `output/data/risk_intel_refresh_log.json`: bounded manual-refresh ledger shape. In Phase 1 the daily batch does not call external Tier 2 web-search providers, so provider counters remain zero unless a later manual-refresh phase explicitly enables them.

Risk intel scoring keeps `raw_score` and final `score` distinct. `score_breakdown` must recompute to `raw_score`; caps such as `inference_only_cap`, `social_only_cap`, and `single_low_quality_source_cap` only limit the final `score`. Edge `confidence` is relationship reliability and is validated against the configured evidence-type confidence bands; source trust contributes to `evidence_strength` instead. Positive `severity_delta` is display context only and does not increase risk score in Phase 1.

The graph status is `ok`, `partial`, `degraded`, or `error` from `input_status` and graph health. A stale `domain_rules[].last_reviewed` older than one year degrades the artifact only when a non-observation alert path references that rule; otherwise it is surfaced in `health_warnings`. Inferred edges must include `inference_refs` pointing at `domain_rules[]`, and every edge needs non-empty `explanation_ko`.

`generation.scoring_config_version` tracks score weights, thresholds, caps, freshness half-life, and hop-decay changes. `generation.confidence_config_version` tracks changes to the default edge confidence range tables. Changes to either config must run the calibration/regression fixtures that assert expected alert levels and confidence bands for each evidence type.

## Schema Version Contract

Machine-readable JSON outputs use `src/output/schema.py::SCHEMA_VERSION` as the output consumer contract version. Root JSON payloads intended for dashboard, API, audit, or automation consumers should include `schema_version` unless they are JSONL records, third-party caches, or legacy compatibility files with a documented exception.

`schema_version` describes output shape, not model version, prompt version, pipeline algorithm version, or data freshness. Backward-compatible additive fields do not require a version bump.

## Web Sync Policy

`output/data` is the source of truth. `web/public/output/data` is a mirror for the static frontend and local Vite development. `web/dist/output/data` is a best-effort mirror only when a build output tree already exists.

Sync failures are logged as output events and should not recompute decisions, mutate state, or make the web layer a source of pipeline logic. Raw logs, caches, SQLite files, and LLM evidence manifests are excluded from the default web mirror.

Operational health checks classify current-facing artifacts separately from historical artifacts. A stale artifact is a current-facing file whose date conflicts with the latest source family, such as a web-only `dashboard.json` with an older `date` or latest `days[].date` than `output/data/index.json.date`. Historical ticker notes, LLM evidence manifests, caches, SQLite files, and CSV state files are not stale solely because they are old. Cleanup remains explicit; health checks report stale candidates before any deletion is considered.

Current-facing source artifacts that cannot expose a root `date` or latest `days[].date` are hard health issues because freshness cannot be determined. Web-only optional legacy artifacts, such as a mirror-only `dashboard.json`, remain warning-level diagnostics until a cleanup policy is explicitly approved.

Sector explorer payloads are refreshed only when the sector scan path runs, such as `python main.py --with-sectors` or the standalone sector CLI. A default `python main.py` run preserves the latest existing `output/data/sectors.json` and mirrored web copies instead of deleting or blanking them.

Core dashboard JSON writes, including `dashboard_history.json`, use the shared safe JSON writer with short retry handling so transient OneDrive or antivirus file locks do not abort the output stage.

`search_evidence.json` is mirrored to `web/public/output/data/search_evidence.json` when present. It is a collector/output evidence artifact and must not be used by web code to override official rule-based decisions. The decision layer may optionally enforce `confidence_meta.search_quality_gate` when `DECISION_SEARCH_QUALITY_GATE_MODE=enforce`; output and web only serialize or display that finalized decision metadata. The payload `provider` is `cache` for cache-only runs and `openai` only when a live provider refresh contributed items. `by_ticker[TICKER]` includes `evidence_status`, `provider_status`, `priority_for_refresh`, `priority_refresh_reasons`, `cache_source_date`, and `cache_age_hours`; `run_summary` includes provider call/error counts, `priority_tickers`, `priority_ticker_count`, `priority_refresh_reasons`, `priority_status_counts`, `priority_refresh_candidate_count`, `cache_ttl_hours`, `stale_cache_hit_count`, and `status_counts` so low evidence can be distinguished from provider failures, stale cache reuse, and priority-refresh targeting remains auditable. The writer uses the shared safe JSON writer, including serialization validation and parse-back, before syncing the web mirror.

`search_audit.json` is mirrored to `web/public/output/data/search_audit.json` when present. It is an observational claim-vs-evidence artifact and must not override official rule-based decisions. The payload includes root metadata, `tickers[]` verdict/count/issue entries, and a typed `run_summary` so audit freshness and claim coverage remain machine-checkable.

`risk_intel_graph.json`, `risk_intel_summary.json`, and `risk_intel_refresh_log.json` are mirrored to `web/public/output/data/` when present. They are read-only risk explanation artifacts for graph/card rendering and must not override official rule-based investment decisions, recompute alerts in the frontend, or trigger provider calls from the output layer. The dashboard may show a compact Korean card summary, while `/risk-intel` renders the fuller Korean network map and health-warning context. `/policy` remains the policy report surface; risk intelligence presents how finalized policy/security/social issues propagate into sectors, holdings, and watchlist tickers.

`backtest_summary.json` is mirrored to `web/public/output/data/backtest_summary.json` when present. It is a read-only performance review artifact for the Backtest page and must not affect official decisions. The payload includes root status/strategy/signal counts, optional direction summaries, optional equity curve points, optional ticker rows, and optional signal metadata.

`monthly_summary.json` is mirrored to `web/public/output/data/monthly_summary.json` when present. It is a read-only monthly review artifact for the Backtest page and monthly note rendering. The payload includes root month/status metadata and, when status is `ok`, typed trading-day, date range, top ticker, and top sector rows.

`routing_outcome.json` is mirrored to `web/public/output/data/routing_outcome.json` when present. It is a read-only routing diagnostics artifact for the Backtest page and performance measurement. The payload includes root run counts, summary metrics, period rows, and an optional latest-run router snapshot with selected tickers, priority skips, router reason codes, and budget estimates.

`performance_baseline.json`, `performance_trends.json`, and `quality_reliability_loop.json` are mirrored to `web/public/output/data/` when present. They are operational measurement artifacts for diagnostics and review, not decision inputs. Frontend consumers must display the finalized values as-is.

The Admin web page may render these performance artifacts as read-only operational KPIs, including priority evidence coverage, evidence cache freshness, Search evidence provider validation fields, BudgetGuard report/enforce review fields, analysis performance quality-loop fields, and `p1_readiness` track statuses from `performance_baseline.json`. The frontend must display the finalized JSON values as-is and must not recompute official decisions, model routing, or factor weights from them.

`analysis_performance.json` is mirrored to `web/public/output/data/` when present. The static web app may display this shadow telemetry, but it must consume the finalized JSON as-is and must not recompute performance metrics or reinterpret official decisions.

Use `python -m src.cli.output_health_check` before committing generated artifacts. The check validates every JSON file under `output/data` and `web/public/output/data`, checks the minimum API status shape including typed provider summaries, LLM usage/cost/model counts, optional quality counters, and ticker matrix provider states, checks the minimum validation warnings shape including typed root metadata, category totals, and category-driven `series[]` count rows, checks the minimum signal quality shape including IC decay, rolling IC, Kelly, and turnover panels while allowing the string `error` fallback payload, checks the minimum search evidence shape including typed cache summary counts, `status_counts`, priority refresh reason/status maps, priority refresh candidate counts, and typed ticker-level status/cache/priority metadata with non-negative `cache_age_hours`, checks the minimum search audit shape including typed run summary counts, ticker verdict/count fields, issue status fields, and bounded `match_score`, checks the minimum backtest summary shape including typed root counts, direction summaries, equity curve points, and ticker rows, checks the minimum monthly summary shape including typed root metadata and `ok`-status top ticker/sector rows, checks the minimum routing outcome shape including typed summary metrics, period rows, and latest-run router metadata, checks the minimum cost log shape including typed `runs[]` and `latest` rows with non-negative profile token/cost counts, routing counts, BudgetGuard counts, and bounded deep-pass cost share, checks the minimum analysis quality shape including typed `runs[]` and `latest` rows with non-negative cost/count values and bounded `hallucination_ratio`, checks the minimum analysis performance shape including summary counts, signal/regime window stats, conviction buckets, factor attribution rows, and action-change contributors, checks the minimum performance artifact shape when those files are present, including typed `performance_baseline.json` root metadata, cost, quality, evidence, signal summaries, optional `p1_readiness` track fields including Search evidence provider validation fields, BudgetGuard review counts, and analysis performance quality-loop fields, checks the minimum `quality_reliability_loop.json` shape including typed summary statuses, decision-quality counts, artifact reliability counts, evidence coverage/status maps, priority refresh counts/maps, report-only cost fields, trend inputs, and warning codes, checks risk intelligence graph artifacts when present including shared `generation.run_id`, score raw/final consistency, configured edge confidence bands, `inference_refs`, stale domain rule warnings, Korean card fields, refresh-log root fields, SQLite store integrity, export manifest hashes, JSON-vs-SQLite row counts, and the rule that SQLite files are excluded from the default web mirror, and typed `performance_trends.json` run rows, detects unresolved merge-conflict markers in output JSON/CSV/Markdown files, and verifies that the default web mirror files match `output/data` byte-for-byte.

## Requirements

* Deterministic output structure
* Stable file naming
* Minimal unnecessary diffs
* Backward-compatible schema extensions when possible

## Constraints

* No data fetching
* No LLM calls
* No decision recomputation

## Rules

* Output formatting must consume finalized data only
* Optional delivery paths such as Slack must not become the source of truth
* Web payload shape should evolve additively unless a planned schema migration is documented
* Committee output is presentation data and must not override rule-based `buy/watch/avoid`
* `pm_view` is presentation data for portfolio review surfaces and must not reinterpret or replace official `buy/watch/avoid`
* Audit checks with no evaluable samples should report `info`, not `pass`, so missing evidence stays visible
