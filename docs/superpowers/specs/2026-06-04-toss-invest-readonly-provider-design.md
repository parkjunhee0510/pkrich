# Toss Invest Read-Only Provider Design

## Goal

Add Toss Invest Open API as a read-only collector source for market data, stock metadata, warnings, exchange rate, and market calendar data while preserving the existing batch pipeline boundaries and avoiding all order/account automation.

## Source

Toss Invest Open API documentation exposes the canonical API server at `https://openapi.tossinvest.com`. The source-of-truth OpenAPI document is `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`.

Relevant endpoints for this phase:

- `POST /oauth2/token`
- `GET /api/v1/prices`
- `GET /api/v1/candles`
- `GET /api/v1/stocks`
- `GET /api/v1/stocks/{symbol}/warnings`
- `GET /api/v1/exchange-rate`
- `GET /api/v1/market-calendar/KR`
- `GET /api/v1/market-calendar/US`

Excluded endpoints:

- account list
- holdings
- orders
- buying power
- sellable quantity
- commissions

## Architecture

The integration stays entirely in the collector layer. A small `TossInvestClient` owns OAuth token issuance, authorized requests, and defensive response parsing. `TossInvestProvider` implements the existing `DataProvider` interface and emits normalized `PartialTickerData` fields consumed by `CollectionOrchestrator`.

The provider is additive and disabled unless `TOSS_INVEST_CLIENT_ID` and `TOSS_INVEST_CLIENT_SECRET` are present. It must never fetch from analyzer, decision, output, state, or web code. It must never call order/account endpoints.

## Normalized Output

The first implementation maps only fields already accepted by `CollectedTickerData`:

- `price`
- `change_percent`
- `currency`
- `volume`
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `day_volume`
- `historical_prices`
- `fundamental_metrics`
- `upcoming_events`
- `technical_indicators`

Unknown Toss response fields remain inside provider-local parsing helpers unless explicitly normalized.

## Cost Rationale

Toss does not expose a news/search endpoint in the current OpenAPI document, so it cannot directly replace OpenAI Web Search evidence in this phase. The expected token benefit comes from improving structured market payloads and enabling later prompt compaction. This phase does not add LLM calls or paid model routes.

## Error Handling

Missing credentials make the provider unavailable. HTTP errors, malformed JSON, empty payloads, and unsupported response shapes return `ProviderResult.failure(...)` and log collector warnings without crashing the pipeline.

## Validation

Focused tests cover token requests, authorized GET requests, normalization, availability gating, and provider failure behavior. Pipeline validation uses targeted collector tests plus `python -m compileall main.py src tests`.
