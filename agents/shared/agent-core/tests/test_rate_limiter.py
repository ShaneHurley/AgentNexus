"""Tests for the sliding-window rate limiter."""
from __future__ import annotations

import os
import threading
import time
import unittest

from agent_core.rate_limiter import RateLimiter, RateLimiterConfig, RateLimitExceeded


class TestRateLimiter(unittest.TestCase):

    def test_allows_calls_within_limit(self):
        rl = RateLimiter(RateLimiterConfig(max_calls=3, window_seconds=10.0))
        for _ in range(3):
            rl.acquire()
        self.assertEqual(rl.remaining(), 0)

    def test_blocks_beyond_limit_then_recovers(self):
        rl = RateLimiter(RateLimiterConfig(
            max_calls=2, window_seconds=0.2, max_wait_seconds=1.0
        ))
        rl.acquire()
        rl.acquire()
        t0 = time.monotonic()
        rl.acquire()  # should block briefly then succeed
        elapsed = time.monotonic() - t0
        self.assertGreaterEqual(elapsed, 0.15)

    def test_error_when_wait_exceeds_max(self):
        rl = RateLimiter(RateLimiterConfig(
            max_calls=1, window_seconds=10.0, max_wait_seconds=0.1
        ))
        rl.acquire()
        with self.assertRaises(RateLimitExceeded):
            rl.acquire()

    def test_disabled_limiter_allows_everything(self):
        rl = RateLimiter(RateLimiterConfig.disabled())
        for _ in range(100):
            rl.acquire()
        self.assertEqual(rl.remaining(), 999)

    def test_thread_safety(self):
        rl = RateLimiter(RateLimiterConfig(max_calls=5, window_seconds=60.0))
        results: list[str] = []
        def worker():
            try:
                rl.acquire()
                results.append("ok")
            except RateLimitExceeded:
                results.append("limited")
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 5)
        self.assertEqual(rl.remaining(), 0)

    def test_report(self):
        rl = RateLimiter(RateLimiterConfig(max_calls=5, window_seconds=60.0))
        rl.acquire()
        rl.acquire()
        report = rl.report()
        self.assertEqual(report["calls_in_window"], 2)
        self.assertEqual(report["remaining"], 3)
        self.assertEqual(report["total_calls"], 2)

    def test_from_profile(self):
        cfg = RateLimiterConfig.from_profile({"rate_limit_calls": 7, "rate_limit_window": 120})
        self.assertEqual(cfg.max_calls, 7)
        self.assertEqual(cfg.window_seconds, 120.0)
        self.assertTrue(cfg.enabled)

    def test_from_profile_defaults(self):
        cfg = RateLimiterConfig.from_profile({})  # no rate_limit_* keys
        self.assertEqual(cfg.max_calls, 10)
        self.assertEqual(cfg.window_seconds, 300.0)
        self.assertTrue(cfg.enabled)

    def test_from_env(self):
        orig_calls = os.environ.get("RF_RATE_LIMIT_CALLS")
        orig_window = os.environ.get("RF_RATE_LIMIT_WINDOW")
        try:
            os.environ["RF_RATE_LIMIT_CALLS"] = "5"
            os.environ["RF_RATE_LIMIT_WINDOW"] = "60"
            cfg = RateLimiterConfig.from_env()
            self.assertEqual(cfg.max_calls, 5)
            self.assertEqual(cfg.window_seconds, 60.0)
        finally:
            if orig_calls is not None:
                os.environ["RF_RATE_LIMIT_CALLS"] = orig_calls
            else:
                os.environ.pop("RF_RATE_LIMIT_CALLS", None)
            if orig_window is not None:
                os.environ["RF_RATE_LIMIT_WINDOW"] = orig_window
            else:
                os.environ.pop("RF_RATE_LIMIT_WINDOW", None)


if __name__ == "__main__":
    unittest.main()
