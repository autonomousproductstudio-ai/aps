"""In-process pub/sub for run lifecycle Events.

The orchestrator publishes Events synchronously (it runs in a plain function / worker
thread, often with no event loop). Each run keeps a **history** so a late SSE subscriber
still gets the whole story via replay, and the CLI can read the full trace after the run.

Event delivery to the API is **push, not poll** (plan 1.3): `publish()` notifies a
`threading.Condition`, and async SSE/WS consumers block on `wait()` (off the event loop via
`run_in_executor`) so progress appears the instant it happens instead of on a 1 s tick. The
condition also serializes history append/read across the worker thread and the loop.
"""
from __future__ import annotations

import asyncio
import threading
from collections import defaultdict

from aps.state.models import Event


class EventBus:
    def __init__(self) -> None:
        self._history: dict[str, list[Event]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        # Guards _history and powers push delivery: producers notify on publish, async
        # consumers wait on it. One condition for the bus is enough — runs are short and
        # consumers filter by run_id on wake.
        self._cond = threading.Condition()

    # ── producer side (sync; safe with or without a running loop) ──────────────
    def publish(self, run_id: str, event: Event) -> None:
        with self._cond:
            self._history[run_id].append(event)
            self._cond.notify_all()        # wake every SSE/WS consumer blocked in wait()
        for q in list(self._subscribers[run_id]):
            try:
                q.put_nowait(event)
            except Exception:
                pass  # a slow/closed subscriber must never break the run

    # ── consumer side ─────────────────────────────────────────────────────────
    def history(self, run_id: str) -> list[Event]:
        with self._cond:
            return list(self._history[run_id])

    def wait(self, run_id: str, seen: int, timeout: float) -> list[Event]:
        """Block until history[run_id] has more than `seen` events, then return the new tail.

        Returns an empty list on timeout (a liveness tick — the caller loops and re-checks its
        own deadline). Designed to be called from a worker thread via `loop.run_in_executor`
        so it never blocks the event loop. This is the push primitive that replaces the poll.
        """
        with self._cond:
            if len(self._history[run_id]) <= seen:
                self._cond.wait(timeout)
            return self._history[run_id][seen:]

    def is_complete(self, run_id: str) -> bool:
        with self._cond:
            return any(e.type in ("run_complete", "run_failed")
                       for e in self._history[run_id])

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Return a queue pre-loaded with the run's history so far, then live events."""
        q: asyncio.Queue = asyncio.Queue()
        with self._cond:
            for ev in self._history[run_id]:
                q.put_nowait(ev)
            self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        with self._cond:
            if q in self._subscribers[run_id]:
                self._subscribers[run_id].remove(q)
