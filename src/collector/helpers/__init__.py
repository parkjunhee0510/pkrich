"""Shared helpers for the collector layer.

These modules exist to break the tangle between providers
(`src/collector/providers/*.py`) and the legacy god-module
`src/collector/price.py`. Providers import pure helpers from here so
that when Phase 1-0e Step 5b retires the legacy path, no provider
breaks.

Modules:
    formatters — pure string/number formatters (no I/O, no side effects)
"""
