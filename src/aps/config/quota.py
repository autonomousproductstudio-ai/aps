"""aps.config.quota — per-provider call ledger + circuit breaker (multipleAPIplan P9).

Two small, thread-safe pieces the failover model and router consult:
  • **Ledger** — counts calls per provider this process, so the router can spread load
    (prefer the least-used provider with room) instead of hammering the head of the chain.
  • **CircuitBreaker** — when a provider errors (429/5xx/…), bench it for a cooldown so the
    chain routes *around* it for a while, then auto-restores. The clock is injectable so the
    behavior is unit-testable without sleeping.

Process-local (no persistence) — exactly what a single run / demo needs.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable


class Ledger:
    """Per-provider cumulative call counter (load-spreading signal for the router)."""

    def __init__(self) -> None:
        self._calls: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record(self, provider: str) -> None:
        with self._lock:
            self._calls[provider] += 1

    def count(self, provider: str) -> int:
        with self._lock:
            return self._calls[provider]

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._calls)


class CircuitBreaker:
    """Bench a provider for `cooldown` seconds after a failure; `is_open` ⇒ skip it for now."""

    def __init__(self, cooldown: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.cooldown = cooldown
        self._clock = clock
        self._until: dict[str, float] = {}
        self._lock = threading.Lock()

    def trip(self, provider: str) -> None:
        with self._lock:
            self._until[provider] = self._clock() + self.cooldown

    def is_open(self, provider: str) -> bool:
        """True while the provider is benched (should be skipped/deprioritized)."""
        with self._lock:
            return self._clock() < self._until.get(provider, 0.0)

    def reset(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._until.clear()
            else:
                self._until.pop(provider, None)


# process-wide singletons used by the failover model
LEDGER = Ledger()
BREAKER = CircuitBreaker()
