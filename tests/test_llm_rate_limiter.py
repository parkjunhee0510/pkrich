from __future__ import annotations

import time
import unittest

from src.collector.rate_limiter import LlmRateLimiter, RateLimiterHub


class LlmRateLimiterTests(unittest.TestCase):
    def test_rpm_alone_when_zero_tokens_requested(self) -> None:
        limiter = LlmRateLimiter(requests_per_minute=60_000, tokens_per_minute=1_000)
        self.assertTrue(limiter.acquire(estimated_tokens=0, timeout=0.05))

    def test_tpm_exhaustion_blocks_until_refill(self) -> None:
        limiter = LlmRateLimiter(
            requests_per_minute=60_000,
            tokens_per_minute=6_000,
            burst_tokens=100,
        )
        self.assertTrue(limiter.acquire(100, timeout=0.01))
        start = time.monotonic()
        acquired = limiter.acquire(50, timeout=1.0)
        elapsed = time.monotonic() - start
        self.assertTrue(acquired)
        self.assertGreater(elapsed, 0.3)

    def test_rejects_tokens_exceeding_capacity(self) -> None:
        limiter = LlmRateLimiter(requests_per_minute=60, tokens_per_minute=1_000, burst_tokens=100)
        with self.assertRaises(ValueError):
            limiter.acquire(200)

    def test_timeout_returns_false(self) -> None:
        limiter = LlmRateLimiter(
            requests_per_minute=60_000,
            tokens_per_minute=600,
            burst_tokens=50,
        )
        self.assertTrue(limiter.acquire(50, timeout=0.01))
        self.assertFalse(limiter.acquire(50, timeout=0.01))


class RateLimiterHubLlmTests(unittest.TestCase):
    def test_register_llm_is_idempotent(self) -> None:
        hub = RateLimiterHub()
        first = hub.register_llm("openai_economy", requests_per_minute=100, tokens_per_minute=10_000)
        second = hub.register_llm("openai_economy", requests_per_minute=999, tokens_per_minute=999)
        self.assertIs(first, second)

    def test_acquire_llm_unregistered_returns_true(self) -> None:
        hub = RateLimiterHub()
        self.assertTrue(hub.acquire_llm("unknown", estimated_tokens=1_000))

    def test_acquire_llm_registered_respects_capacity(self) -> None:
        hub = RateLimiterHub()
        hub.register_llm(
            "openai_deep",
            requests_per_minute=60_000,
            tokens_per_minute=600,
            burst_tokens=50,
        )
        self.assertTrue(hub.acquire_llm("openai_deep", estimated_tokens=50, timeout=0.01))
        self.assertFalse(hub.acquire_llm("openai_deep", estimated_tokens=50, timeout=0.01))

    def test_multiple_llm_providers_independent(self) -> None:
        hub = RateLimiterHub()
        hub.register_llm("openai_economy", requests_per_minute=60_000, tokens_per_minute=600, burst_tokens=50)
        hub.register_llm("openai_deep", requests_per_minute=60_000, tokens_per_minute=600, burst_tokens=50)
        self.assertTrue(hub.acquire_llm("openai_economy", estimated_tokens=50, timeout=0.01))
        self.assertTrue(hub.acquire_llm("openai_deep", estimated_tokens=50, timeout=0.01))


if __name__ == "__main__":
    unittest.main()
