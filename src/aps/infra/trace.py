"""Per-tool event sink carried in a ContextVar (plan §4 observability).

Tools emit `tool_call` / `tool_result` (with timing) through whatever sink the active run
installed — without threading a bus/run_id into all 52 tools. The research fan-out's
`copy_context()` propagates the sink into its worker threads, so parallel sub-researchers'
tool calls stream too. When no run installed a sink (CLI, tests, a bare tool call) `emit` is a
no-op. This is what unlocks the frontend's live tool stream and per-tool latency in the trace.
"""
from __future__ import annotations

import contextvars
from typing import Callable

_SINK: contextvars.ContextVar[Callable[[str, dict], None] | None] = contextvars.ContextVar(
    "aps_event_sink", default=None)


def set_sink(fn: Callable[[str, dict], None] | None) -> contextvars.Token:
    """Install the per-run event sink for the current context. Returns a reset token."""
    return _SINK.set(fn)


def reset(token: contextvars.Token) -> None:
    _SINK.reset(token)


def emit(type_: str, data: dict) -> None:
    """Forward an event to the active run's sink, if any. Never raises."""
    fn = _SINK.get()
    if fn is not None:
        try:
            fn(type_, data)
        except Exception:
            pass
