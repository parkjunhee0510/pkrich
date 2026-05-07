# Testing and Validation

## Codex Routing

- Read when choosing verification scope or adding tests for a touched layer.
- Pair with the layer doc for the code under change.
- Then inspect `tests/` and run the smallest useful command before broader validation.

## Core Requirement

Pipeline must run end-to-end.

## Validation Checklist

### Execution

* Pipeline completes without errors

### Output

* Files generated correctly
* Formats valid
* `python -m src.cli.output_health_check` passes when generated artifacts or web-public data are committed

### State

* Portfolio calculations correct
* Signal tracking updated properly

### Storage

* Data stored correctly
* Backend consistency maintained

### Logging

* Events recorded correctly
* Summary generated

### Cost

* No unnecessary API usage

## Failure Policy

* Continue on non-critical failure
* Fail only on critical pipeline break

## Strategy

* Prefer integration testing
* Validate real pipeline behavior
* When implementation changes behavior or contracts, update related docs in the same change set
* For output schema changes, add shape or serialization coverage before updating generated fixtures
* For audit checks, cover both evaluable samples and insufficient-data paths

## Notable Test Modules

* `tests/test_macro_v2.py` - macro v2 pipeline (surprise, events, narrative)
* `tests/test_macro_event_match.py` - macro event matching helpers
* `tests/test_model_config.py` - module-specific model profiles and batch sizes
* `tests/test_decision_factors.py` - factor scoring including macro regime/event factors
* `tests/test_decision_registry.py` - factor registry resolution
* `tests/test_output.py` - output serialization, including news reference provenance fields
* `tests/test_output_schema.py` - generated JSON shape stability and web-public operational copies
* `tests/test_pipeline_quality_wiring.py` - pipeline wiring for quality outputs and API status run-date behavior
* `tests/test_search_evidence.py` - search evidence cache normalization, output serialization, and web-public mirror coverage
* `tests/eval/` - LLM audit data loading, replay, report rendering, and check-specific thresholds
* `tests/test_codex_*hook*.py` and `tests/test_codex_summarize_session.py` - local Codex hook regression coverage
