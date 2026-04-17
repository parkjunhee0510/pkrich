"""Provider registry — the lookup table Orchestrator uses to route requests.

Responsibilities:
  * Own the canonical list of registered DataProvider instances.
  * Resolve, per data type, the ordered list of providers that emit it
    (sorted by ascending priority; ties broken by registration order).
  * Filter by availability — `is_available()` gates whether a provider
    participates in this run (missing API keys, disabled flags, etc.).

The registry does NOT execute providers. It is a pure lookup. The
Orchestrator (orchestrator.py) consumes this ordering and runs them with
rate-limiting, caching, and error handling.

Deterministic ordering is critical: reproducible runs depend on fallback
chains being stable across pipeline executions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.collector.base import DataProvider

logger = logging.getLogger(__name__)


@dataclass
class _RegisteredProvider:
    """Internal bookkeeping — tracks registration order for stable sorting."""
    provider: DataProvider
    registration_index: int


class ProviderRegistry:
    """Registry of DataProvider instances, indexed by data type.

    Thread-safety note: register() is typically called once at pipeline
    startup, so we don't bother with locking. If that assumption changes,
    wrap _providers in a Lock.
    """

    def __init__(self) -> None:
        self._providers: list[_RegisteredProvider] = []
        self._by_name: dict[str, DataProvider] = {}

    def register(self, provider: DataProvider) -> None:
        """Register a provider. Names must be unique; re-registering raises."""
        if not provider.name:
            raise ValueError(f"Provider {type(provider).__name__} has no name")

        if provider.name in self._by_name:
            raise ValueError(f"Provider name {provider.name!r} already registered")

        self._by_name[provider.name] = provider
        self._providers.append(
            _RegisteredProvider(
                provider=provider,
                registration_index=len(self._providers),
            )
        )
        logger.debug(
            "Registered provider name=%s priority=%d provides=%s",
            provider.name, provider.priority, sorted(provider.provides),
        )

    def get(self, name: str) -> DataProvider | None:
        """Fetch a provider by name (useful for direct invocation in tests)."""
        return self._by_name.get(name)

    def all(self) -> list[DataProvider]:
        """Return every registered provider in registration order."""
        return [rp.provider for rp in self._providers]

    def providers_for(
        self,
        data_type: str,
        *,
        only_available: bool = True,
    ) -> list[DataProvider]:
        """Return providers that emit `data_type`, sorted by priority.

        Ties on priority are broken by registration order — the first
        provider registered wins, so calling code can express preference
        by registration sequence when priorities match.

        only_available: When True, providers whose is_available() is False
                        are filtered out. Set False for diagnostic queries.
        """
        matches = [
            rp for rp in self._providers
            if data_type in rp.provider.provides
        ]

        if only_available:
            matches = [rp for rp in matches if _safe_is_available(rp.provider)]

        matches.sort(key=lambda rp: (rp.provider.priority, rp.registration_index))
        return [rp.provider for rp in matches]

    def data_types(self) -> set[str]:
        """Return the union of all data types across registered providers."""
        result: set[str] = set()
        for rp in self._providers:
            result.update(rp.provider.provides)
        return result


def _safe_is_available(provider: DataProvider) -> bool:
    """is_available() must not raise, but defensively isolate it anyway."""
    try:
        return provider.is_available()
    except Exception as err:  # noqa: BLE001
        logger.warning(
            "Provider %r is_available() raised: %s — treating as unavailable",
            provider.name, err,
        )
        return False


__all__ = ["ProviderRegistry"]
