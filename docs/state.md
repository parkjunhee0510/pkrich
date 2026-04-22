# State Management

## Purpose

Maintain reproducible derived state across pipeline runs.

## Current Responsibilities

### Signal Tracking

* Record newly generated signals per ticker and run date
* Update `1d`, `5d`, and `20d` return windows from stored price history
* Maintain signal statistics used by the decision layer, backtests, and admin views

### Outcome Labeling

* Maintain classical return-window evaluation
* Maintain triple-barrier outcome labels as an additive path

### Portfolio-Derived State

* Compute portfolio summary inputs for analysis and output
* Support portfolio-risk-aware decision adjustments

## Source Of Truth

State must come from:
* stored history in datastore
* current collected prices
* deterministic recomputation

State must not come from:
* live APIs during the state step
* manually edited opaque snapshots

## Rules

* State must be reproducible
* State updates must be idempotent at the run level
* No formatting logic in this layer
* No hidden business rules that should live in analyzer or decision
