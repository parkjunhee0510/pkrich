# CLAUDE.md

Guidance for Claude Code working in this repo.

## Commands

```bash
# Pipeline
python main.py                              # Daily pipeline
python -m src.cli.run_sectors               # Sector scan only (no LLM)
python -m src.utils.migrate_csv_to_sqlite   # CSV→SQLite
uvicorn src.api.main:app --reload           # FastAPI

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
```

| Stage | Role | Modules |
|-------|------|---------|
| collect | Only stage that hits external APIs (prices/news/fundamentals/filings/options) | `src/collector/` |
| analyze | Batched LLM research notes + ensemble consensus; pure function of collected data | `src/analyzer/` |
| decide  | Market regime + per-ticker buy/watch/avoid + conviction (rule-based, no LLM) | `src/decision/` |
| store   | Persist signals/returns/routing to CSV or SQLite | `src/utils/datastore*.py`, `signal_tracker.py` |
| output  | Markdown / JSON / Slack / sector scan / AB test (read-only downstream) | `src/output/`, `_run_sector_scan` |
| log     | `record_pipeline_event` JSONL stream across all stages | `src/utils/pipeline_logging.py` |

Entry: `src/pipeline.py::run_pipeline`. `_run_sector_scan` is isolated so sector outages never fail the main flow.

### Core types (`src/types.py`, frozen dataclasses)
`WatchlistItem`, `CollectedTickerData`, `TickerAnalysis`, `TickerDecision` (action + conviction 0–100), `MarketRegime` (risk_on/neutral/risk_off), `PortfolioSummary` / `PortfolioPosition`.

### Key modules
| Path | Purpose |
|------|---------|
| `src/collector/price.py` | yfinance → Stooq fallback |
| `src/collector/macro.py` | VIX, DXY, copper, bonds |
| `src/collector/sector_scan.py` | 1y history + benchmark ETF, no LLM |
| `src/analyzer/research_note.py` | Batched LLM notes |
| `src/decision/decision_layer.py` | 8-factor conviction scoring |
| `src/decision/market_regime.py` | Regime detection |
| `src/decision/factor_audit.py` / `tune_weights.py` | Audit + Spearman grid search |
| `src/output/json_export.py` | `dashboard.json` + `_sync_web_public_data` |
| `src/output/sectors_json.py` | `sectors.json` for `/sectors` |
| `src/output/markdown.py` | Daily/weekly/ticker notes |
| `src/utils/datastore.py` | CSV/SQLite backend abstraction |
| `src/utils/signal_tracker.py` | Signals + 1D/5D/20D return backfill |
| `src/utils/config.py` | YAML loader |

### Web frontend (`web/`, React + TS, read-only)
Key files: `hooks/useDashboardData.ts`, `hooks/useSectorsData.ts`, `pages/{Dashboard,TickerDetail,Sectors,SectorDetail}.tsx`, `components/DecisionCard.tsx`, `types/index.ts` (mirrors `src/types.py`). No write API — all data comes from the Python pipeline.

### Config (`config/`)
`watchlist.yaml` (tickers/news/CIK/IR), `portfolio.yaml` (holdings), `models.yaml` (LLM profiles), `output.yaml`, `providers.yaml`, `decision_weights.yaml` (regime-conditional), `sectors.yaml` (read-only `/sectors`: ticker list + `news_keywords` + optional `benchmark_etf`).

### Env (`.env`)
Required: `OPENAI_API_KEY`. Optional: `OPENAI_MODEL_PROFILE` (economy/standard/deep), `SLACK_WEBHOOK_URL`, `DATASTORE_BACKEND` (csv/sqlite), `ENABLE_CONVICTION_ROUTING`, `ALPHAVANTAGE_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`, `POLYGON_API_KEY`.

### Output layout
```
output/daily/YYYY-MM-DD.md, weekly/YYYY-Www.md, tickers/{TICKER}/YYYY-MM-DD.md
output/data/  dashboard.json, dashboard_history.json (90d), sectors.json,
              price_history.{csv,json}, signal_tracker.csv, ticker_timelines.json
logs/pipeline/YYYY-MM-DD.jsonl
```

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
