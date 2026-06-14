"""Per-host circuit breaker (plan 2.5).

When a source (Reddit, a flaky API) keeps failing, retrying every call burns retry budget and
latency on a corpse. After `threshold` consecutive failures a key's breaker OPENS for
`cooldown` seconds — calls fail fast (`CircuitOpen`) so the tool degrades to its fixture
immediately instead of waiting through three backed-off retries. After the cooldown one trial
is allowed (half-open); success closes the breaker, another failure re-opens it.

Thread-safe and hand-rolled — no pybreaker dependency. Pairs with the existing retry + rate
limiter (the retry/cache/breaker/timeout resilience quartet).
"""
from __future__ import annotations

import threading
import time


class CircuitOpen(Exception):
    """Raised when a call is short-circuited because its host breaker is open."""


class CircuitBreaker:
    def __init__(self, threshold: int = 5, cooldown: float = 30.0) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self._fails: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """False while the key's breaker is open (within its cooldown); True otherwise — a True
        after the cooldown is the single half-open trial."""
        with self._lock:
            until = self._open_until.get(key, 0.0)
            return not (until and time.monotonic() < until)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)
            self._open_until.pop(key, None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            n = self._fails.get(key, 0) + 1
            self._fails[key] = n
            if n >= self.threshold:
                self._open_until[key] = time.monotonic() + self.cooldown

    def state(self, key: str) -> str:
        """'closed' | 'open' | 'half_open' — for observability (breaker-state panel)."""
        with self._lock:
            if self._open_until.get(key, 0.0) > time.monotonic():
                return "open"
            return "half_open" if self._fails.get(key) else "closed"
