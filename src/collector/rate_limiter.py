"""Central token-bucket rate limiter for data provider API calls.

Design goals:
  * One `TokenBucketLimiter` instance per provider (e.g. yfinance, FMP).
  * Thread-safe — Phase 1-1 will enable ThreadPoolExecutor parallel collection.
  * Monotonic-clock based to avoid wall-clock jumps (NTP, DST) causing
    spurious waits or under-limits.
  * No asyncio dependency: the collector pipeline is sync, and token buckets
    compose fine with sync code via short sleeps.

Algorithm: Standard token bucket.
  * Bucket has `burst` capacity, refills at `rate_per_second = cpm / 60`.
  * acquire() blocks the caller until 1 token is available.
  * try_acquire() returns immediately; caller can decide to skip or retry.

The `RateLimiterHub` multiplexes limiters by provider name and is the
single object the Orchestrator injects into each provider.
"""
from __future__ import annotations

import logging
import threading
import time

from src.collector.base import RateLimit

logger = logging.getLogger(__name__)


class TokenBucketLimiter:
    """Thread-safe token bucket rate limiter.

    Tokens accumulate at `rate_per_second` up to `burst` capacity.
    `acquire()` removes 1 token, blocking if none are available.
    """

    def __init__(self, rate_limit: RateLimit) -> None:
        if rate_limit.calls_per_minute <= 0:
            raise ValueError(f"calls_per_minute must be positive, got {rate_limit.calls_per_minute}")
        self._rate_per_second = rate_limit.calls_per_minute / 60.0
        self._capacity = float(rate_limit.effective_burst)
        self._tokens = float(rate_limit.effective_burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        """Refill tokens based on elapsed monotonic time. Caller must hold lock."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate_per_second)
            self._last_refill = now

    def try_acquire(self) -> bool:
        """Non-blocking acquire. Returns True if a token was taken, else False."""
        with self._lock:
            self._refill_locked()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def acquire(self, timeout: float | None = None) -> bool:
        """Block until 1 token is available or timeout elapses.

        Returns True if acquired, False if timed out.
        timeout=None means wait indefinitely.
        """
        deadline = time.monotonic() + timeout if timeout is not None else None

        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # How long until we have 1 token?
                needed = 1.0 - self._tokens
                wait_seconds = needed / self._rate_per_second

            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait_seconds = min(wait_seconds, remaining)

            # Sleep outside the lock so other threads can also check.
            time.sleep(max(0.001, wait_seconds))

    @property
    def available_tokens(self) -> float:
        """Current token count (snapshot; not synchronized for caller decisions)."""
        with self._lock:
            self._refill_locked()
            return self._tokens


class RateLimiterHub:
    """Registry of per-provider TokenBucketLimiter instances.

    Orchestrator creates one hub per pipeline run and passes it to providers
    indirectly (via its own collect_for wrapper). Providers never touch this
    directly — the orchestrator acquires tokens on their behalf.
    """

    def __init__(self) -> None:
        self._limiters: dict[str, TokenBucketLimiter] = {}
        self._lock = threading.Lock()

    def register(self, provider_name: str, rate_limit: RateLimit) -> TokenBucketLimiter:
        """Register a provider's limiter. Idempotent — returns existing one if any."""
        with self._lock:
            if provider_name in self._limiters:
                return self._limiters[provider_name]
            limiter = TokenBucketLimiter(rate_limit)
            self._limiters[provider_name] = limiter
            logger.debug(
                "RateLimiter registered provider=%s cpm=%d burst=%d",
                provider_name,
                rate_limit.calls_per_minute,
                rate_limit.effective_burst,
            )
            return limiter

    def get(self, provider_name: str) -> TokenBucketLimiter | None:
        with self._lock:
            return self._limiters.get(provider_name)

    def acquire(self, provider_name: str, timeout: float | None = None) -> bool:
        """Convenience: acquire a token for the given provider.

        Returns False if the provider is not registered (caller should
        treat this as "no throttling applies" rather than an error).
        """
        limiter = self.get(provider_name)
        if limiter is None:
            return True
        return limiter.acquire(timeout=timeout)


__all__ = ["TokenBucketLimiter", "RateLimiterHub"]
