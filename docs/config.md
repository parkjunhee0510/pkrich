# Configuration

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
