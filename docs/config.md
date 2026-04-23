# Configuration

## Codex Routing

- Read when the task changes YAML config structure, config loading, or environment-driven behavior.
- Pair with the relevant layer doc instead of using this file alone for business logic changes.
- Then inspect `config/` files and `src/utils/config.py`.

## Watchlist

* Location: `config/watchlist.yaml`
* Single source of truth for tickers

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
