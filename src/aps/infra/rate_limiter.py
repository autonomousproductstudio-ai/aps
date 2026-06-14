"""Per-source rate limiter (TRD C4). NOT a counted tool — platform capability.

A token-bucket keyed by source name (e.g. "github", "reddit") so one slow/over-eager
source can't blow another's free-tier quota. `acquire(source)` blocks just long enough
to stay under `rpm` requests/minute for that source, then returns.

Thread-safe, dependency-free (stdlib `time`/`threading`), monotonic clock.
"""
from __future__ import annotations

import threading
import time


class _Bucket:
    __slots__ = ("capacity", "tokens", "refill_per_sec", "updated")

    def __init__(self, rpm: int) -> None:
        self.capacity = float(max(1, rpm))
        self.tokens = float(max(1, rpm))
        self.refill_per_sec = max(1, rpm) / 60.0
        self.updated = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.updated
        self.updated = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)

    def take(self) -> float:
        """Consume one token; return seconds the caller should sleep first (>=0)."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        deficit = 1.0 - self.tokens
        wait = deficit / self.refill_per_sec
        self.tokens = 0.0
        return wait


class RateLimiter:
    """Token-bucket limiter, one bucket per source key."""

    def __init__(self, rpm: int = 60) -> None:
        self.rpm = rpm
        self._buckets: dict[str, _Bucket] = {}
        self._overrides: dict[str, int] = {}
        self._lock = threading.Lock()

    def configure(self, source: str, rpm: int) -> None:
        """Set a per-source rpm that differs from the default."""
        with self._lock:
            self._overrides[source] = rpm
            self._buckets.pop(source, None)

    def _bucket(self, source: str) -> _Bucket:
        b = self._buckets.get(source)
        if b is None:
            b = _Bucket(self._overrides.get(source, self.rpm))
            self._buckets[source] = b
        return b

    def acquire(self, source: str, *, block: bool = True) -> float:
        """Reserve one slot for `source`. Sleeps to honor the rate when block=True;
        returns the wait time (seconds) that was (or would be) required."""
        with self._lock:
            wait = self._bucket(source).take()
        if wait > 0 and block:
            time.sleep(wait)
        return wait
