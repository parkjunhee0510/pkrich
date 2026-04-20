"""Bootstrap: build a fully-wired CollectionOrchestrator from YAML config.

This is the single entry point pipeline.py will call to get an orchestrator.
Keeping it in one place makes it easy to diff old vs new collection paths
during migration (Phase 1-0e Step 3).

Usage:
    from src.collector.bootstrap import build_orchestrator
    orchestrator = build_orchestrator()
    collected, report = orchestrator.collect_all(watchlist, run_date)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.collector.base import DataProvider, RateLimit
from src.collector.cache import ResponseCache
from src.collector.orchestrator import CollectionOrchestrator, DEFAULT_CACHE_TTL_HOURS
from src.collector.rate_limiter import RateLimiterHub
from src.collector.registry import ProviderRegistry

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path("config/providers.yaml")
_CACHE_PATH = Path("output/data/api_cache.sqlite")


@dataclass(frozen=True)
class ProviderConfig:
    """Per-provider YAML config entry."""
    priority: int
    rate_limit: RateLimit


def load_provider_config(path: Path | str = _CONFIG_PATH) -> dict[str, ProviderConfig]:
    """Parse config/providers.yaml into a dict[name, ProviderConfig].

    Missing file → returns empty dict (allowing unit tests to run without
    the config in place). Individual providers can choose fallback defaults.
    """
    config_path = Path(path)
    if not config_path.exists():
        logger.warning("Provider config not found at %s — using defaults", config_path)
        return {}

    try:
        with config_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as err:
        logger.error("Failed to parse %s: %s", config_path, err)
        return {}

    providers_section = raw.get("providers", {}) or {}
    result: dict[str, ProviderConfig] = {}
    for name, entry in providers_section.items():
        if not isinstance(entry, dict):
            continue
        try:
            rate = int(entry.get("rate", 30))
            burst = entry.get("burst")
            result[name] = ProviderConfig(
                priority=int(entry.get("priority", 99)),
                rate_limit=RateLimit(
                    calls_per_minute=rate,
                    burst=int(burst) if burst is not None else None,
                ),
            )
        except (TypeError, ValueError) as err:
            logger.warning("Bad config for provider %s: %s", name, err)
    return result


def load_cache_ttl(path: Path | str = _CONFIG_PATH) -> dict[str, float]:
    """Load cache TTL overrides. Falls back to DEFAULT_CACHE_TTL_HOURS."""
    config_path = Path(path)
    merged = dict(DEFAULT_CACHE_TTL_HOURS)
    if not config_path.exists():
        return merged

    try:
        with config_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError:
        return merged

    overrides = raw.get("cache_ttl", {}) or {}
    for data_type, hours in overrides.items():
        try:
            merged[str(data_type)] = float(hours)
        except (TypeError, ValueError):
            continue
    return merged


def apply_config_to_provider(
    provider: DataProvider,
    config: dict[str, ProviderConfig],
) -> DataProvider:
    """Mutate a provider instance with config-driven priority and rate limit.

    Providers carry sensible class-level defaults; this lets YAML override
    them without editing Python. If no config entry exists, defaults stand.
    """
    entry = config.get(provider.name)
    if entry is None:
        return provider
    provider.priority = entry.priority
    provider.rate_limit = entry.rate_limit
    return provider


def build_orchestrator(
    providers: list[DataProvider] | None = None,
    *,
    config_path: Path | str = _CONFIG_PATH,
    cache_path: Path | str | None = _CACHE_PATH,
    max_workers: int | None = None,
) -> CollectionOrchestrator:
    """Construct a CollectionOrchestrator with registry + rate hub + cache.

    `providers`: If None, an empty orchestrator is returned. During Phase
    1-0 Step 2, the caller passes the list of DataProvider instances to
    register. Once all providers are extracted (Step 4+), we can introspect
    `src/collector/providers/` and auto-discover.

    `cache_path`: Pass None to disable caching (useful in tests).

    `max_workers`: Phase 1-1 parallel ticker collection. None or 1 →
    sequential (legacy behaviour). Values > 1 enable a ThreadPoolExecutor
    across tickers — the rate limiter and cache are already thread-safe.
    """
    config = load_provider_config(config_path)
    cache_ttl = load_cache_ttl(config_path)

    registry = ProviderRegistry()
    if providers:
        for provider in providers:
            apply_config_to_provider(provider, config)
            registry.register(provider)

    rate_hub = RateLimiterHub()
    cache = ResponseCache(cache_path) if cache_path is not None else None

    return CollectionOrchestrator(
        registry=registry,
        rate_hub=rate_hub,
        cache=cache,
        cache_ttl_hours=cache_ttl,
        max_workers=max_workers,
    )


__all__ = [
    "ProviderConfig",
    "apply_config_to_provider",
    "build_orchestrator",
    "load_cache_ttl",
    "load_provider_config",
]
