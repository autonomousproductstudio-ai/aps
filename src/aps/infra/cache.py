"""Read-through TTL cache for retrieval tool results (plan 1.2).

Repeated/overlapping queries — the same idea re-run in a demo, or two concurrent runs
researching the same space — otherwise re-hit GitHub/HN/web for identical results and
compete for the same rate-limited sources. Caching keyed on `(tool_name, normalized_args)`
turns a cold run into a warm one (~5–10 s) and lets concurrent runs SHARE evidence instead
of contending for free-tier quota.

Right-sized for the demo: an in-process `cachetools.TTLCache` (LRU + TTL), zero infra. The
production swap is Redis with per-source TTLs (execution plan §1.2 / Phase 4); this module is
the single seam where that swap happens, so nothing above it changes.

Only RETRIEVAL tools are cached (network I/O, hashable str/int/list args). Analysis tools are
deterministic, cheap, and take `list[Evidence]` (not usefully hashable), so they are never
cached — the integration point in `tools.base.BaseTool.run` enforces that.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any, Callable

from cachetools import TTLCache

from aps.infra.logging import get_logger

_LOG = get_logger("aps.cache")

_TTL_SECONDS = int(os.getenv("APS_TOOL_CACHE_TTL", "900"))      # 15 min
_MAXSIZE = int(os.getenv("APS_TOOL_CACHE_MAXSIZE", "512"))

# Disabled under pytest so the hermetic suite never shares state across cases; the cache
# primitive itself is tested directly (it re-reads this flag). APS_TOOL_CACHE=false turns it
# off in any environment.
_ENABLED = (os.getenv("APS_TOOL_CACHE", "true").lower() == "true"
            and "pytest" not in sys.modules)

# Per-TTL cache buckets. The default (900s) serves the retrieval tools; slow-changing sources
# (domain/trademark 6h, compliance 24h — plan Phase 4/5) ask for a longer TTL via the tool's
# `cache_ttl` attribute, which routes to (and lazily creates) its own bucket. cachetools.TTLCache
# holds a single TTL per instance, so one bucket per distinct TTL is the clean way to mix them.
_caches: dict[int, TTLCache] = {_TTL_SECONDS: TTLCache(maxsize=_MAXSIZE, ttl=_TTL_SECONDS)}
_lock = threading.Lock()
_hits = 0
_misses = 0


def enabled() -> bool:
    """Whether the read-through cache is active in this process."""
    return _ENABLED


def _bucket(ttl: int | None) -> TTLCache:
    """The cache bucket for `ttl` seconds (default when None), created on first use. Caller
    holds `_lock`."""
    t = int(ttl) if ttl else _TTL_SECONDS
    c = _caches.get(t)
    if c is None:
        c = TTLCache(maxsize=_MAXSIZE, ttl=t)
        _caches[t] = c
    return c


def _key(tool_name: str, kwargs: dict) -> str:
    try:
        norm = json.dumps(kwargs, sort_keys=True, default=str)
    except Exception:
        norm = repr(sorted(kwargs.items(), key=lambda kv: kv[0]))
    return f"{tool_name}|{norm}"


def get_or_call(tool_name: str, kwargs: dict, compute: Callable[[], Any],
                ttl: int | None = None) -> Any:
    """Return the cached value for `(tool_name, kwargs)`, else compute it and store it.

    `ttl` (seconds) selects the cache bucket — slow-changing sources pass a long TTL so repeat
    runs are near-free; None uses the default bucket. The `compute()` call runs OUTSIDE the lock
    so concurrent misses for *different* keys don't serialize their network I/O behind one
    another. Two racing misses for the SAME key may both compute once (a benign double-fetch);
    the last write wins — acceptable for a read-through cache and far cheaper than holding the
    lock across the network call.
    """
    global _hits, _misses
    key = _key(tool_name, kwargs)
    with _lock:
        bucket = _bucket(ttl)
        if key in bucket:
            _hits += 1
            return bucket[key]
        _misses += 1
    result = compute()
    with _lock:
        _bucket(ttl)[key] = result
    _LOG.debug("tool_cache_miss", tool=tool_name, ttl=ttl or _TTL_SECONDS)
    return result


def stats() -> dict:
    """Hit/miss/size snapshot — feeds observability (queue depth / cache hit-rate panel)."""
    with _lock:
        total = _hits + _misses
        size = sum(len(c) for c in _caches.values())
        return {"hits": _hits, "misses": _misses, "size": size,
                "hit_rate": round(_hits / total, 3) if total else 0.0}


def clear() -> None:
    """Drop all entries (every bucket) and reset counters (used by tests and warm-restart)."""
    global _hits, _misses
    with _lock:
        for c in _caches.values():
            c.clear()
        _hits = 0
        _misses = 0
