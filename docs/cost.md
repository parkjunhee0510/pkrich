# Cost Management

## Goal

Maintain minimal operational cost while preserving output quality.

## LLM Strategy

* Batch multiple tickers
* Use smallest viable model
* Reduce prompt size aggressively
* Avoid redundant calls

## Data Strategy

* Prefer free APIs
* Use fallback chains instead of paid redundancy

## Compute Strategy

* Avoid recomputation
* Reuse cached or stored results when valid

## Constraints

* No expensive models without explicit instruction
* No paid dependencies unless justified

## Trade-offs

* Prefer cost over marginal accuracy
* Prefer simplicity over optimization complexity
