# Utils

## Codex Routing

- Read when the task touches shared helpers under `src/utils/` that support multiple layers without owning a domain workflow.
- Do not use this file as the primary doc for datastore, logging, or state changes that already have dedicated docs.
- Then inspect only the specific helper modules involved.

## Responsibilities

* Shared helpers that do not own end-to-end business workflows
* Common computations reused across layers
* Configuration and model-selection helpers used by analyzer and pipeline code

## Current Shared Helpers

* `macro_sensitivity.py`: portfolio and ticker macro sensitivity computations
* `ticker_macro_beta.py`: ticker-level macro beta estimation
* `macro_event_match.py`: macro event matching helpers used by macro v2 factors; sector and industry scoring rules are loaded from `config/macro_event_rules.yaml`
* `model_config.py`: module-specific model profiles and batch sizes
* `budget_guard.py`: shared BudgetGuard config parsing, optional LLM path cost estimates, and shadow/enforce decisions

## Must Not

* Become a hidden domain layer
* Take ownership of decision, analyzer, output, or persistence workflows
* Accumulate business logic that belongs in a dedicated layer

## Boundary Notes

* If a helper starts defining user-visible behavior, move that logic back to its owning layer doc and module
* Datastore helpers belong under `docs/datastore.md`, not here
* Pipeline logging helpers belong under `docs/logging.md`, not here
