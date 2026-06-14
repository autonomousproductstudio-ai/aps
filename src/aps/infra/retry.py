"""Retry wrapper for transient tool I/O (NFR-4). NOT a counted tool.

`with_retry` decorates a callable so transient failures (network blips, 5xx) are
retried with exponential backoff. Uses Tenacity when installed; falls back to a small
hand-rolled exponential-backoff loop otherwise, so the decorator works in any env.

Retries are bounded (default 3 attempts) and only catch the exception types passed in
(default: anything) — a retry policy, never an infinite loop.
"""
from __future__ import annotations

import functools
import time
from typing import Callable

DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.2  # seconds; small so tests stay fast


def with_retry(
    fn: Callable | None = None,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """Decorate `fn` to retry on `exceptions` with exponential backoff.

    Usable bare (`@with_retry`) or parameterized (`@with_retry(attempts=5)`).
    """
    def decorate(func: Callable) -> Callable:
        try:
            from tenacity import (  # optional dependency
                retry,
                stop_after_attempt,
                wait_exponential,
                retry_if_exception_type,
            )

            wrapped = retry(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(multiplier=base_delay, min=base_delay, max=5),
                retry=retry_if_exception_type(exceptions),
                reraise=True,
            )(func)
            return functools.wraps(func)(wrapped)
        except Exception:
            # Fallback: minimal exponential-backoff loop, same semantics.
            @functools.wraps(func)
            def loop(*args, **kwargs):
                last: BaseException | None = None
                for i in range(attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:  # type: ignore[misc]
                        last = e
                        if i < attempts - 1:
                            time.sleep(base_delay * (2 ** i))
                assert last is not None
                raise last
            return loop

    # bare-decorator support: @with_retry
    if callable(fn):
        return decorate(fn)
    return decorate
