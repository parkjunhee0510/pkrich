# Configuration

## Codex Routing

- Read when the task changes YAML config structure, config loading, or environment-driven behavior.
- Pair with the relevant layer doc instead of using this file alone for business logic changes.
- Then inspect `config/` files and `src/utils/config.py`.

## Watchlist

* Location: `config/watchlist.yaml`
* Single source of truth for tickers

## Sector Explorer

* Location: `config/sectors.yaml`
* Read-only sector explorer grouping for theme/sector cards
* Each sector should define `id`, display `name`, optional `description`, optional `benchmark_etf`, `news_keywords`, and a balanced ticker list
* Display `name` and `description` values are Korean for the sector explorer UI; `news_keywords` stay mostly English to preserve source search quality
* Energy coverage uses `benchmark_etf: XLE` and should avoid duplicating utility/grid infrastructure names already tracked under power-grid style themes
* Materials/critical minerals, cloud/enterprise software, and transport/logistics are default expansion sectors for macro sensitivity, enterprise IT spending, and freight-cycle coverage

## Rules

* No hardcoding of:

  * tickers
  * company names
  * API keys
  * URLs

## Secrets

* Must come from environment variables

## Environment

* Separate config from code
* Keep configuration minimal and explicit

## Validation

* Ensure config is loaded correctly
* Fail early on invalid configuration
