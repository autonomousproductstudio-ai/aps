"""Cooperative cancellation signal for a run (plan 2.2 / 2.3).

Daemon threads can't be killed, so cancellation is cooperative: the run polls a per-run
"should I stop?" check at its own boundaries (between graph stages and before each research
tool round) and unwinds cleanly when it flips.

The check is carried in a ContextVar rather than threaded through every call signature — the
same mechanism the per-run model override uses, and it propagates into the research fan-out's
`copy_context()` workers for free. `RunCancelled` derives from BaseException so the broad
`except Exception` guards in the supervisor / graph nodes do NOT swallow it (mirroring
asyncio.CancelledError) — it unwinds straight to `run_sync`, which records the terminal state.
"""
from __future__ import annotations

import contextvars
from typing import Callable

_CHECK: contextvars.ContextVar[Callable[[], bool] | None] = contextvars.ContextVar(
    "aps_cancel_check", default=None)


class RunCancelled(BaseException):
    """Raised to unwind a run when its cancel signal is set."""


def set_check(fn: Callable[[], bool] | None) -> contextvars.Token:
    """Install the per-run cancel check for the current context. Returns a reset token."""
    return _CHECK.set(fn)


def reset(token: contextvars.Token) -> None:
    _CHECK.reset(token)


def is_cancelled() -> bool:
    """True when the active run has been asked to stop. Never raises."""
    fn = _CHECK.get()
    try:
        return bool(fn and fn())
    except Exception:
        return False


def checkpoint() -> None:
    """Raise RunCancelled if the active run has been cancelled — call at a safe boundary."""
    if is_cancelled():
        raise RunCancelled()
