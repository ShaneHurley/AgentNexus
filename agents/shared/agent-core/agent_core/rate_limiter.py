"""Sliding-window rate limiter for API call throttling.

Shared by Research Forge and Daily Coder. Zero external dependencies
beyond stdlib. Thread-safe for parallel research lanes.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class RateLimiterConfig:
    """Rate limit configuration."""
    max_calls: int = 10
    window_seconds: float = 300.0
    max_wait_seconds: float = 300.0
    enabled: bool = True

    @classmethod
    def from_profile(cls, profile: dict[str, Any], *, overrides: dict[str, Any] | None = None) -> "RateLimiterConfig":
        """Build from a budget profile dict (YAML or JSON)."""
        ov = overrides or {}

        def _get_val(key: str, default: Any) -> Any:
            v = ov.get(key)
            if v is None:
                v = profile.get(key)
            return default if v is None else v

        return cls(
            max_calls=int(_get_val("rate_limit_calls", 10)),
            window_seconds=float(_get_val("rate_limit_window", 300.0)),
            max_wait_seconds=float(_get_val("rate_limit_max_wait", 300.0)),
            enabled=bool(_get_val("rate_limit_enabled", True)),
        )

    @classmethod
    def from_env(cls) -> "RateLimiterConfig":
        """Build from environment variables (standalone / CLI usage)."""
        return cls(
            max_calls=int(os.environ.get("RF_RATE_LIMIT_CALLS", "10")),
            window_seconds=float(os.environ.get("RF_RATE_LIMIT_WINDOW", "300")),
            max_wait_seconds=float(os.environ.get("RF_RATE_LIMIT_MAX_WAIT", "300")),
            enabled=os.environ.get("RF_RATE_LIMIT_ENABLED", "true").lower() not in ("0", "false", "no"),
        )

    @classmethod
    def disabled(cls) -> "RateLimiterConfig":
        return cls(enabled=False)


class RateLimitExceeded(RuntimeError):
    """Raised when rate limit wait timeout is exceeded."""
    def __init__(self, message: str, *, calls: int, window: float):
        self.calls = calls
        self.window = window
        super().__init__(message)


class RateLimiter:
    """Thread-safe sliding-window rate limiter.

    Tracks timestamps of recent calls in a deque and blocks (sleeps) when
    the window is full. If sleeping would exceed ``max_wait_seconds``,
    raises ``RateLimitExceeded``.
    """

    def __init__(self, config: RateLimiterConfig) -> None:
        self.config = config
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()
        self._total_calls: int = 0
        self._total_waits: int = 0
        self._total_wait_seconds: float = 0.0

    def acquire(self) -> None:
        """Block until a slot is available, or raise RateLimitExceeded."""
        if not self.config.enabled:
            return

        if self.config.max_calls <= 0:
            raise RateLimitExceeded(
                f"Rate limit: {self.config.max_calls} calls permitted; quota exhausted",
                calls=self.config.max_calls,
                window=self.config.window_seconds,
            )

        deadline = time.monotonic() + self.config.max_wait_seconds

        with self._lock:
            self._evict_expired()
            if len(self._timestamps) < self.config.max_calls:
                self._timestamps.append(time.monotonic())
                self._total_calls += 1
                return

        # slow path — wait for a slot
        while True:
            with self._lock:
                self._evict_expired()
                if len(self._timestamps) < self.config.max_calls:
                    self._timestamps.append(time.monotonic())
                    self._total_calls += 1
                    return

                if not self._timestamps:
                    wait_until = time.monotonic() + 0.05
                else:
                    wait_until = self._timestamps[0] + self.config.window_seconds
                now = time.monotonic()

                if wait_until > deadline:
                    raise RateLimitExceeded(
                        f"Rate limit: {self.config.max_calls} calls / "
                        f"{self.config.window_seconds}s window exhausted; "
                        f"max wait {self.config.max_wait_seconds}s exceeded",
                        calls=self.config.max_calls,
                        window=self.config.window_seconds,
                    )

                sleep_for = max(0.05, wait_until - now + 0.01)
                self._total_waits += 1
                self._total_wait_seconds += sleep_for

            time.sleep(sleep_for)

    def remaining(self) -> int:
        """Calls remaining in the current window."""
        if not self.config.enabled:
            return 999
        with self._lock:
            self._evict_expired()
            return max(0, self.config.max_calls - len(self._timestamps))

    def report(self) -> dict[str, Any]:
        with self._lock:
            self._evict_expired()
            return {
                "enabled": self.config.enabled,
                "max_calls": self.config.max_calls,
                "window_seconds": self.config.window_seconds,
                "calls_in_window": len(self._timestamps),
                "remaining": max(0, self.config.max_calls - len(self._timestamps)),
                "total_calls": self._total_calls,
                "total_waits": self._total_waits,
                "total_wait_seconds": round(self._total_wait_seconds, 2),
            }

    def _evict_expired(self) -> None:
        cutoff = time.monotonic() - self.config.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
