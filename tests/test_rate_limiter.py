"""Unit tests for src/collector/rate_limiter.py."""
from __future__ import annotations

import threading
import time
import unittest

from src.collector.base import RateLimit
from src.collector.rate_limiter import RateLimiterHub, TokenBucketLimiter


class TokenBucketLimiterTests(unittest.TestCase):
    def test_initial_burst_tokens_available(self) -> None:
        limiter = TokenBucketLimiter(RateLimit(calls_per_minute=60, burst=5))
        # 5 burst tokens should be immediately consumable.
        for _ in range(5):
            self.assertTrue(limiter.try_acquire())
        # 6th non-blocking acquire should fail.
        self.assertFalse(limiter.try_acquire())

    def test_acquire_blocks_until_refill(self) -> None:
        # 120 cpm = 2 tokens/sec, burst 1 → second acquire should wait ~0.5s.
        limiter = TokenBucketLimiter(RateLimit(calls_per_minute=120, burst=1))
        self.assertTrue(limiter.acquire(timeout=0.1))
        start = time.monotonic()
        acquired = limiter.acquire(timeout=2.0)
        elapsed = time.monotonic() - start
        self.assertTrue(acquired)
        # Expect ~0.5s wait; give generous leeway to tolerate CI jitter.
        self.assertGreaterEqual(elapsed, 0.3)
        self.assertLess(elapsed, 1.5)

    def test_acquire_times_out(self) -> None:
        limiter = TokenBucketLimiter(RateLimit(calls_per_minute=60, burst=1))
        self.assertTrue(limiter.acquire(timeout=0.1))
        # Refill rate = 1/sec; 0.05s timeout → cannot acquire.
        self.assertFalse(limiter.acquire(timeout=0.05))

    def test_invalid_rate_raises(self) -> None:
        with self.assertRaises(ValueError):
            TokenBucketLimiter(RateLimit(calls_per_minute=0))

    def test_thread_safety(self) -> None:
        """Many threads contending on a small bucket must never over-issue.

        Uses a negligible refill rate (1 cpm ≈ 0.017 tokens/sec) so the bucket
        cannot gain a whole token during the test window — the only tokens
        available are the initial burst. Since acquire's check+decrement runs
        under a lock, EXACTLY `burst` of the 50 contending threads may succeed:
        no more (would be a race) and no fewer (would be lost tokens).

        (The previous 6000 cpm = 100 tokens/sec refilled a few tokens during
        thread startup jitter, making `sum <= burst` flaky on loaded machines.)
        """
        limiter = TokenBucketLimiter(RateLimit(calls_per_minute=1, burst=10))
        successes: list[bool] = []
        lock = threading.Lock()

        def worker():
            ok = limiter.try_acquire()
            with lock:
                successes.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Deterministic now that refill is ~0: exactly the burst capacity.
        self.assertEqual(sum(successes), 10)


class RateLimiterHubTests(unittest.TestCase):
    def test_register_is_idempotent(self) -> None:
        hub = RateLimiterHub()
        a = hub.register("yfinance", RateLimit(calls_per_minute=60))
        b = hub.register("yfinance", RateLimit(calls_per_minute=999))  # ignored
        self.assertIs(a, b)

    def test_acquire_unknown_provider_returns_true(self) -> None:
        """Unregistered providers are treated as 'no throttling' — must not block."""
        hub = RateLimiterHub()
        self.assertTrue(hub.acquire("unknown"))

    def test_multiple_providers_independent(self) -> None:
        hub = RateLimiterHub()
        hub.register("a", RateLimit(calls_per_minute=60, burst=1))
        hub.register("b", RateLimit(calls_per_minute=60, burst=1))
        self.assertTrue(hub.acquire("a"))
        # Even though "a" is empty, "b" still has tokens.
        self.assertTrue(hub.acquire("b"))


if __name__ == "__main__":
    unittest.main()
