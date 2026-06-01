# CLAUDE.md

Guidance for Claude Code working in this repo.

## Commands

```bash
# Pipeline
python main.py                              # Daily pipeline
python -m src.cli.run_sectors               # Sector scan only (no LLM)
python -m src.cli.output_health_check       # Validate output artifact integrity
python -m src.cli.write_performance_outputs # Refresh performance_* artifacts
python -m src.utils.migrate_csv_to_sqlite   # CSV→SQLite
uvicorn src.api.main:app --reload           # FastAPI

# Evaluation harness
python -m src.eval.runner                   # Run D/I/O/R checks against latest run

# Tests
python -m unittest discover -s tests -v
python -m unittest tests.test_fallback_analysis -v   # single
python -m compileall main.py src tests               # syntax

# Web (React SPA, GitHub Pages)
cd web && npm install && npm run dev        # http://localhost:5173
cd web && npm run build
```

## Architecture

Daily batch stock research. Strict layer order:

```
collect → analyze → decide → store → output
              └──── log (cross-cutting) ────┘
              └──── eval (post-run audit) ──┘
```

| Stage | Role | Modules |
|-------|------|---------|
| collect | Only stage that hits external APIs (prices/news/fundamentals/filings/options) | `src/collector/` |
| analyze | Batched LLM research notes + ensemble consensus + per-module analyzers | `src/analyzer/`, `src/analyzer/modules/` |
| decide  | Market regime + per-ticker buy/watch/avoid + conviction (rule-based, no LLM) | `src/decision/`, `src/decision/factors/` |
| store   | Persist signals/returns/routing to CSV or SQLite | `src/utils/datastore*.py`, `signal_tracker.py` |
| output  | Markdown / JSON / Slack / sector scan / AB test / risk intel graph (read-only downstream) | `src/output/`, `_run_sector_scan` |
| log     | `record_pipeline_event` JSONL stream across all stages | `src/utils/pipeline_logging.py` |
| eval    | D/I/O/R post-run checks (drift, missingness, schema, retries) — read-only | `src/eval/`, `src/eval/checks/` |

Entry: `src/pipeline.py::run_pipeline`. `_run_sector_scan` is isolated so sector outages never fail the main flow. Risk Intelligence Graph (`src/output/risk_intel_*`) is a downstream output subsystem — degrades to `partial`/`degraded` rather than failing the pipeline (see `output/data/risk_intel_*.json` and spec `docs/superpowers/specs/2026-05-19-risk-intelligence-graph-design.md`).

### Core types (`src/types.py`, frozen dataclasses)
`WatchlistItem`, `CollectedTickerData`, `TickerAnalysis`, `TickerDecision` (action + conviction 0–100), `MarketRegime` (risk_on/neutral/risk_off), `PortfolioSummary` / `PortfolioPosition`.

### Key modules
| Path | Purpose |
|------|---------|
| `src/collector/price.py` | yfinance → Stooq fallback |
| `src/collector/macro.py`, `macro_events.py`, `macro_surprise.py` | VIX/DXY/copper/bonds + macro calendar + surprise scoring |
| `src/collector/sector_scan.py` | 1y history + benchmark ETF, no LLM |
| `src/collector/policy_events.py` | Stage 1: web_search policy events (trusted-domain filter, dedupe cache) |
| `src/collector/news_*` (8 files), `ir_rss.py`, `cache.py` | Multi-source news (RSS/search/shadow-compare) + IR feeds + collector cache |
| `src/collector/{finnhub,fmp}.py`, `helpers/{earnings,sector_etf,yfinance_helpers}.py` | Paid-provider adapters + collector helpers |
| `src/analyzer/policy_impact.py` | Stage 2: ticker impact mapping + tailwind aggregation |
| `src/analyzer/research_note.py`, `committee.py`, `ensemble.py` | Batched LLM notes + committee + ensemble consensus |
| `src/analyzer/llm_runtime.py`, `smart_router.py`, `validator.py`, `evidence_manifest.py` | LLM execution runtime, model routing, output validation, evidence audit |
| `src/analyzer/modules/{news,peer_comparison,portfolio_risk,research_narrative,risk_assessment}_module.py` | Per-aspect analyzer modules (composable, batched) |
| `src/analyzer/macro_narrative.py`, `weekly_insight.py`, `signal_levels.py`, `ab_test.py`, `search_audit.py` | Narrative synthesis + weekly summaries + signal trigger levels + A/B + search audit |
| `src/decision/decision_layer.py` | 13-factor conviction scoring (see `src/decision/factors/`) |
| `src/decision/market_regime.py` | Regime detection (risk_on/neutral/risk_off) |
| `src/decision/{calibration,confidence,data_quality,scorer,registry,triple_barrier,search_quality,signal_quality}.py` | Decision support: calibration, confidence shaping, data-quality gates, scorer/registry |
| `src/decision/factor_audit.py`, `tune_weights.py` | Audit + Spearman grid search for weight tuning |
| `src/decision/factors/` | 13 factors: `valuation, momentum, fundamentals, catalyst, earnings, news_tone, peer_rank, signal_record, macro_event, macro_regime, regime, policy_tailwind, portfolio_risk` |
| `src/output/markdown.py` | Daily/weekly/ticker markdown notes |
| `src/output/sectors_json.py` | `sectors.json` for `/sectors` |
| `src/output/policy_json.py`, `policy_active_events.py` | `policy_impact.json` + active policy events feed |
| `src/output/risk_intel_{builder,config,scoring,json,exporter,store}.py` | Risk Intel Graph: nodes/edges/alert_paths, scoring config, JSON writers, SQLite cache |
| `src/output/{api_status,analysis_quality,analysis_performance,cost_log,routing_outcome,direction_alignment,performance,pm_view}.py` | Per-artifact JSON writers |
| `src/output/{search_audit_json,search_evidence_json}.py` | Search audit + evidence artifacts |
| `src/output/health_*.py` (~14 modules) | Per-artifact health checks (status: ok/partial/degraded/error) |
| `src/output/{schema,sharded_export,web_sync_contract,slack,alert,ab_test}.py` | Output schema, sharded exports, web/Slack/alert dispatch, A/B results |
| `src/eval/runner.py`, `eval/checks/{d,i,o,r}*.py` | Post-run drift/input/output/retry evaluation harness |
| `src/utils/datastore{,_csv,_sqlite}.py` | CSV/SQLite backend abstraction |
| `src/utils/signal_tracker.py`, `signal_metadata_backfill.py` | Signals + 1D/5D/20D return backfill |
| `src/utils/{config,env,model_config,token_budget,token_estimator,budget_guard,cost_tracker}.py` | Config/env/model/token/cost plumbing |
| `src/utils/{earnings_history,earnings_pattern,quarterly_financials,sec_filings,news_tone,macro_event_match,macro_sensitivity,ticker_macro_beta,period_changes,portfolio,portfolio_risk,performance_analytics,performance_metrics,ticker_timelines,monthly_summary,weekly_summary}.py` | Domain utility functions |
| `src/backtester/engine.py` | Backtest engine (signals → returns) |
| `src/chat/engine.py` | Local research/chat engine |
| `src/api/main.py`, `src/cli/*.py` | FastAPI + CLI entry points (`run_sectors`, `output_health_check`, `write_performance_outputs`, etc.) |

### Web frontend (`web/`, React + TS, read-only)
- **Pages** (`web/src/pages/`): `Dashboard, TickerDetail, Sectors, SectorDetail, PolicyImpact, RiskIntel, Portfolio, PriceHistory, Signals, Calendar, Scenario, Backtest, Chat, Admin, ApiStatus, NotFound`.
- **Hooks** (`web/src/hooks/`): `useDashboardData, useSectorsData, usePolicyData, useRiskIntelData, useTickerAnalysis, useTickerHistory, useTickerTimeline, usePriceHistory, usePriceHistoryLive, useLocalPortfolioEditor, useLocalResearchAutomation, useJsonResource`.
- **Components** (`web/src/components/`): `DecisionCard, MarketOverview, MarketRegimeBanner, MacroContextBar, MacroNarrativePanel, MarketMoodSectorBriefing, NewsItem, PerformanceMeasurementPanel, PortfolioActionsReview, PortfolioCommandCenter, PortfolioRiskPanel, PriceChart, RiskIntelPanel, SearchEvidenceBadge, SecFilingBadges, SectorBenchmark, SectorPerformanceBars, SectorSummary, SignalBadge, SignalQualityPanel, Skeleton, Sparkline, TodayDecisionStrip, TraderDashboardPanels, TraderDecisionBoard, WatchlistTable, Layout`.
- **Data layer** (`web/src/data/`): `DashboardRepository.ts`, `StaticJsonRepository.ts` (reads `output/data/*.json`).
- **Types** (`web/src/types/index.ts`) mirror `src/types.py`.
- No write API — all data comes from the Python pipeline; static JSON only.

### Config (`config/`)
`watchlist.yaml` (tickers/news/CIK/IR), `portfolio.yaml` (holdings), `models.yaml` (LLM profiles), `output.yaml`, `providers.yaml`, `decision_weights.yaml` (regime-conditional), `sectors.yaml` (read-only `/sectors`: ticker list + `news_keywords` + optional `benchmark_etf`), `policy_sources.yaml` (trusted-domain whitelist for policy web search), `search_evidence.yaml` (search audit settings), `ticker_policy_context.yaml` (per-ticker policy exposure hints).

### Env (`.env`)
Required: `OPENAI_API_KEY`. Optional: `OPENAI_MODEL_PROFILE` (economy/standard/deep), `SLACK_WEBHOOK_URL`, `DATASTORE_BACKEND` (csv/sqlite), `ENABLE_CONVICTION_ROUTING`, `ALPHAVANTAGE_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`, `POLYGON_API_KEY`.

### Output layout
```
output/daily/YYYY-MM-DD.md, weekly/YYYY-Www.md
output/tickers/{TICKER}/YYYY-MM-DD.md                       # per-ticker markdown
output/data/
  # core
  dashboard_history.json (90d rolling), sectors.json, index.json,
  price_history.{csv,json,sqlite}, signal_tracker.csv, ticker_timelines.json,
  tickers/{TICKER}/{history,latest}.json                    # per-ticker JSON shards
  # quality / health
  api_status.json, api_ticker_matrix.{csv,json},
  analysis_quality.json, validation_warnings.json,
  cost_log.json, routing_outcome.json, routing_log{,_history}.json,
  performance_baseline.json, performance_trends.json, analysis_performance.json,
  monthly_summary.json, backtest_summary.json, calibration.json,
  factor_audit.json, tuning_report.json, signal_quality.json,
  direction_alignment.json, ab_test_results.json
  # search/policy
  search_audit.json, search_evidence.json,
  policy_impact.json, policy_active_events.json, policy_events_cache.json
  # risk intelligence graph
  risk_intel_graph.json, risk_intel_summary.json, risk_intel_refresh_log.json,
  risk_intel.sqlite
  # caches / history
  analysis_history.sqlite, api_cache.sqlite
logs/pipeline/YYYY-MM-DD.jsonl
```
Schemas: see `tests/fixtures/output_schemas/*.shape.json` for canonical shapes.

## Principles
- Daily batch only — no streaming.
- GitHub Actions runs Python business logic, not shell scripts.
- Free data sources preferred; paid APIs are optional enrichment.

## Operational rules
@.claude/rules/layer-separation.md
@.claude/rules/graceful-degradation.md
@.claude/rules/pipeline-logging.md
@.claude/rules/frozen-dataclass-contracts.md
@.claude/rules/output-source-of-truth.md
@.claude/rules/sector-explorer-readonly.md
@.claude/rules/config-driven.md
@.claude/rules/testing.md
