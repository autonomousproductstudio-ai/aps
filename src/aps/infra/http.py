"""Resilient HTTP for retrieval tools — the one sanctioned way to make a live call.

Wraps `requests` with the three infra concerns the tool layer needs:
- **rate limiting** — a per-host token bucket so one source can't burn another's
  free-tier quota (TRD C4),
- **retry** — Tenacity exponential backoff on transient transport errors (NFR-4),
- **logging** — a structured line per attempt/failure (NFR-3).

`get`/`post` are drop-in replacements for `requests.get`/`requests.post` (same
kwargs: params, headers, json, timeout, ...), so a tool only swaps `requests` for
`http`. The source key is derived from the URL host automatically; pass `source=` to
override. Retries cover transport errors (connection/timeout), not 4xx/5xx — the tool
still calls `raise_for_status()` and handles HTTP status itself.
"""
from __future__ import annotations

import os
import re

import requests

from aps.infra.retry import with_retry
from aps.infra.rate_limiter import RateLimiter
from aps.infra.breaker import CircuitBreaker, CircuitOpen
from aps.infra.logging import get_logger

DEFAULT_TIMEOUT = 15
_HOST = re.compile(r"^https?://([^/:]+)", re.IGNORECASE)

# Process-wide limiter; default 60 req/min/host, generous for free tiers as a safety net.
_LIMITER = RateLimiter(rpm=60)
# Per-host circuit breaker (plan 2.5): trip after N consecutive transport failures so a dead
# source fails fast to its fixture instead of burning the retry budget on every call.
_BREAKER = CircuitBreaker(threshold=int(os.getenv("APS_BREAKER_THRESHOLD", "5")),
                          cooldown=float(os.getenv("APS_BREAKER_COOLDOWN", "30")))
_LOG = get_logger("aps.http")

_TRANSIENT = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def _host(url: str) -> str:
    m = _HOST.match(url or "")
    return m.group(1).lower() if m else "unknown"


def configure_rate(source: str, rpm: int) -> None:
    """Set a per-source (host) rate different from the default."""
    _LIMITER.configure(source, rpm)


def request(method: str, url: str, *, source: str | None = None,
            attempts: int = 3, **kwargs) -> requests.Response:
    """Rate-limited, retried HTTP request. Returns the `requests.Response`."""
    src = source or _host(url)
    # Circuit breaker (2.5): if this host's breaker is open, fail fast — don't acquire a rate
    # token or spend three retries on a source we already know is down.
    if not _BREAKER.allow(src):
        _LOG.warning("http_circuit_open", source=src, url=url)
        raise CircuitOpen(f"circuit open for {src}")
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    _LIMITER.acquire(src)

    @with_retry(attempts=attempts, base_delay=0.3, exceptions=_TRANSIENT)
    def _do() -> requests.Response:
        return requests.request(method, url, **kwargs)

    try:
        resp = _do()
    except _TRANSIENT as e:
        _BREAKER.record_failure(src)   # count toward tripping the breaker for this host
        _LOG.warning("http_transient_failure", source=src, url=url, error=str(e))
        raise
    _BREAKER.record_success(src)       # a good response closes/clears the breaker
    return resp


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)
