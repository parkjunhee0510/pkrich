# Testing and Validation

## Core Requirement

Pipeline must run end-to-end.

## Validation Checklist

### Execution

* Pipeline completes without errors

### Output

* Files generated correctly
* Formats valid

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

## Notable Test Modules

* `tests/test_macro_v2.py` — macro v2 pipeline (surprise, events, narrative)
* `tests/test_macro_event_match.py` — macro event matching helpers
* `tests/test_model_config.py` — module-specific model profiles and batch sizes
* `tests/test_decision_factors.py` — factor scoring including macro regime/event factors
* `tests/test_decision_registry.py` — factor registry resolution
