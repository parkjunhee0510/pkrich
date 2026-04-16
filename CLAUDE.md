# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Python Pipeline
```bash
python main.py                          # Run daily pipeline
python -m unittest discover -s tests -v # Run all tests
python -m compileall main.py src tests  # Syntax check
python -m src.utils.migrate_csv_to_sqlite  # CSV→SQLite migration
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
collect → analyze → output
```

**Never** call external APIs from `analyzer/` or `output/`. All data collection happens in `collector/`.

### Pipeline flow (`src/pipeline.py`)
1. Load `config/watchlist.yaml` and `config/portfolio.yaml`
2. `src/collector/` — fetch price/financials/news/filings/options
3. `src/analyzer/research_note.py` — batch LLM analysis (OpenAI)
4. `src/decision/` — rule-based buy/watch/avoid scoring (no LLM)
5. `src/output/` — write Markdown/JSON/Slack/alerts
6. Sync JSON files to `web/public/output/data/` for the React dashboard

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
| `src/analyzer/research_note.py` | Batched LLM research notes |
| `src/decision/decision_layer.py` | 8-factor conviction scoring (pure rule-based) |
| `src/decision/market_regime.py` | Market regime detection |
| `src/output/json_export.py` | Produces `dashboard.json` for React frontend |
| `src/output/markdown.py` | Daily/weekly/ticker Markdown notes |
| `src/utils/datastore.py` | Datastore abstraction (CSV or SQLite backend) |
| `src/utils/signal_tracker.py` | Signal recording + 1D/5D/20D return backfill |
| `src/utils/config.py` | YAML config loader (watchlist, portfolio, models) |

### Web frontend (`web/`)
React + TypeScript SPA served as static files (deployed to GitHub Pages).
- `web/src/hooks/useDashboardData.ts` — merges `dashboard.json` + `dashboard_history.json`
- `web/src/pages/Dashboard.tsx` — main watchlist view
- `web/src/pages/TickerDetail.tsx` — per-ticker detail with price chart
- `web/src/components/DecisionCard.tsx` — buy/watch/avoid badge display
- Data is read-only (no write API from frontend); all updates come from the Python pipeline

### Configuration files
| File | Purpose |
|------|---------|
| `config/watchlist.yaml` | Tickers, news keywords, SEC CIK, IR RSS feeds |
| `config/portfolio.yaml` | Holdings (shares, avg_cost) |
| `config/models.yaml` | LLM model profiles (economy/standard/deep) |
| `config/output.yaml` | News source limits, IR brand names |
| `config/decision_weights.yaml` | Factor weights for decision scoring |

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
    ├── price_history.csv / .json
    ├── signal_tracker.csv
    └── ticker_timelines.json
```

## Design Principles
- Batch architecture: run once daily, no streaming
- All external API failures → graceful degradation (never crash pipeline)
- `output/` is source of truth; Obsidian is a mirror
- GitHub Actions runs business logic (defined in Python), not shell scripts
- Free data sources preferred; paid APIs are optional enrichment
