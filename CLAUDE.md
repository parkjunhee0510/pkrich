# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Python Pipeline
```bash
python main.py                          # Run daily pipeline
python -m unittest discover -s tests -v # Run all tests
python -m compileall main.py src tests  # Syntax check
python -m src.utils.migrate_csv_to_sqlite  # CSV→SQLite migration
python -m src.cli.run_sectors           # Sector explorer scan only (no LLM/decision)
uvicorn src.api.main:app --reload       # Start FastAPI server
```

### Web Dashboard
```bash
cd web && npm install   # Install dependencies
cd web && npm run dev   # Dev server → http://localhost:5173/
cd web && npm run build # Production build
```

### Single test
```bash
python -m unittest tests.test_fallback_analysis -v
```

## Architecture

This is a **daily batch stock research automation** system. The pipeline has a strict layer separation:

```
collect → analyze → decide → store → output
               └──── log (cross-cutting) ────┘
```

| Stage | What it does | Modules |
|-------|--------------|---------|
| **collect** | Fetch prices / news / fundamentals / filings / options. Only this stage hits external APIs. | `src/collector/` |
| **analyze** | Batch LLM research notes + ensemble consensus. Pure function of collected data. | `src/analyzer/` |
| **decide** | Market regime + per-ticker buy/watch/avoid + conviction score. Rule-based, no LLM. | `src/decision/` |
| **store** | Persist signals, returns, routing logs into CSV or SQLite (`output/data/*`). | `src/utils/datastore*.py`, `src/utils/signal_tracker.py` |
| **output** | Write Markdown / JSON / Slack / alerts / sector scan / AB test payload. Read-only downstream view. | `src/output/`, `_run_sector_scan` |
| **log** | `record_pipeline_event` stream (JSONL) spans every stage for observability + failure forensics. | `src/utils/pipeline_logging.py` |

### Pipeline flow (`src/pipeline.py::run_pipeline`)
1. **Bootstrap** — `load_dotenv`, `start_pipeline_logging`, load `config/watchlist.yaml` + `config/portfolio.yaml`, open datastore
2. **Collect** — `_collect_market_context` (price + macro + market overview + historical prices) and `collect_news_for_watchlist` (or `NewsOrchestrator`)
3. **State prep** — `calculate_portfolio_summary`, `attach_portfolio_macro_sensitivity`, `load_recent_signals`, `load_peer_candidates`, `detect_market_regime`
4. **Analyze** — `AnalysisEnsemble.analyze_with_consensus` → per-ticker analyses + consensus verdicts
5. **Store (interim)** — `datastore.update_signal_returns` backfills 1D/5D/20D returns on historical signals
6. **Decide** — `generate_decisions` + `apply_consensus_to_decisions` produces `TickerDecision` list (action + conviction)
7. **Store (final)** — `datastore.record_signals` persists today's signals (with decision + regime)
8. **Output** — `write_outputs` (Markdown + `dashboard.json` + ticker notes), `write_ab_test_results`, `_run_sector_scan`, `send_daily_summary` (Slack). `json_export` also calls `_sync_web_public_data` to copy into `web/public/output/data/`.
9. **Log** — `record_pipeline_event` runs throughout; `_run_sector_scan` is isolated so a sector outage never fails the main flow.

### Core types (`src/types.py`)
All data flows through frozen dataclasses:
- `WatchlistItem` — ticker config
- `CollectedTickerData` — raw market data (price, fundamentals, news, options)
- `TickerAnalysis` — LLM output (summary, signals, news references)
- `TickerDecision` — decision layer output (action: buy/watch/avoid, conviction 0-100)
- `MarketRegime` — market environment (risk_on/neutral/risk_off)
- `PortfolioSummary` / `PortfolioPosition` — portfolio P&L

### Key modules
| Path | Purpose |
|------|---------|
| `src/collector/price.py` | yfinance → Stooq fallback price collection |
| `src/collector/macro.py` | Macro context (VIX, DXY, copper, bonds) |
| `src/collector/sector_scan.py` | Sector explorer price + news collector (1y history, benchmark ETF, no LLM) |
| `src/analyzer/research_note.py` | Batched LLM research notes |
| `src/decision/decision_layer.py` | 8-factor conviction scoring (pure rule-based) |
| `src/decision/market_regime.py` | Market regime detection |
| `src/decision/factor_audit.py` | Factor collinearity / look-ahead audit |
| `src/decision/tune_weights.py` | Weight tuning grid search (Spearman optimization) |
| `src/output/json_export.py` | Produces `dashboard.json` + `_sync_web_public_data` helper |
| `src/output/sectors_json.py` | Produces `sectors.json` for the `/sectors` page |
| `src/output/markdown.py` | Daily/weekly/ticker Markdown notes |
| `src/cli/run_sectors.py` | Standalone entry point for sector-only refresh |
| `src/utils/datastore.py` | Datastore abstraction (CSV or SQLite backend) |
| `src/utils/signal_tracker.py` | Signal recording + 1D/5D/20D return backfill |
| `src/utils/config.py` | YAML config loader (watchlist, portfolio, models, sectors) |

### Web frontend (`web/`)
React + TypeScript SPA served as static files (deployed to GitHub Pages).
- `web/src/hooks/useDashboardData.ts` — merges `dashboard.json` + `dashboard_history.json`
- `web/src/hooks/useSectorsData.ts` — fetches `sectors.json` for the sector explorer
- `web/src/pages/Dashboard.tsx` — main watchlist view
- `web/src/pages/TickerDetail.tsx` — per-ticker detail with price chart
- `web/src/pages/Sectors.tsx` — sector explorer list
- `web/src/pages/SectorDetail.tsx` — per-sector page (benchmark ETF overlay + correlation heatmap + ticker cards)
- `web/src/components/DecisionCard.tsx` — buy/watch/avoid badge display
- `web/src/types/index.ts` — shared TypeScript types mirroring `src/types.py`
- Data is read-only (no write API from frontend); all updates come from the Python pipeline

### Configuration files
| File | Purpose |
|------|---------|
| `config/watchlist.yaml` | Tickers, news keywords, SEC CIK, IR RSS feeds |
| `config/portfolio.yaml` | Holdings (shares, avg_cost) |
| `config/models.yaml` | LLM model profiles (economy/standard/deep) |
| `config/output.yaml` | News source limits, IR brand names |
| `config/providers.yaml` | External data provider settings |
| `config/decision_weights.yaml` | Factor weights for decision scoring (regime-conditional) |
| `config/sectors.yaml` | Sector groupings for the read-only `/sectors` page (ticker list + `news_keywords` + optional `benchmark_etf`) |

### Environment variables (`.env`)
- `OPENAI_API_KEY` — required
- `OPENAI_MODEL_PROFILE` — selects profile from `config/models.yaml` (default: `economy`)
- `SLACK_WEBHOOK_URL` — optional Slack notifications
- `DATASTORE_BACKEND` — `csv` (default) or `sqlite`
- `ENABLE_CONVICTION_ROUTING` — `true` routes high-conviction tickers to deep model
- Optional data enrichment: `ALPHAVANTAGE_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`, `POLYGON_API_KEY`

### Output structure
```
output/
├── daily/YYYY-MM-DD.md          # Daily research note
├── daily/weekly/YYYY-Www.md     # Weekly summary
├── tickers/{TICKER}/YYYY-MM-DD.md
└── data/
    ├── dashboard.json            # Latest day (React reads this)
    ├── dashboard_history.json    # Rolling 90-day history
    ├── sectors.json              # Sector explorer payload
    ├── price_history.csv / .json
    ├── signal_tracker.csv
    └── ticker_timelines.json
logs/
└── pipeline/YYYY-MM-DD.jsonl    # record_pipeline_event stream
```

## Sector Explorer
- Config: `config/sectors.yaml`.
- Collector: `src/collector/sector_scan.py` — 1y daily close + up to 5 Google News RSS items + optional `benchmark_etf`.
- Output: `output/data/sectors.json` via `src/output/sectors_json.py`.
- Ad-hoc refresh: `python -m src.cli.run_sectors` (`--all`, `--sectors`, `--date`, `--no-sync`).
- Frontend pages: `/sectors`, `/sectors/:id`. All metrics computed client-side from `sectors.json`.
- Behavioral rules — see `@.claude/rules/sector-explorer-readonly.md`.

## Design Principles
- Batch architecture: run once daily, no streaming
- GitHub Actions runs business logic (defined in Python), not shell scripts
- Free data sources preferred; paid APIs are optional enrichment

Operational rules are split into `.claude/rules/`:
@.claude/rules/layer-separation.md
@.claude/rules/graceful-degradation.md
@.claude/rules/pipeline-logging.md
@.claude/rules/frozen-dataclass-contracts.md
@.claude/rules/output-source-of-truth.md
@.claude/rules/sector-explorer-readonly.md
@.claude/rules/config-driven.md
@.claude/rules/testing.md
