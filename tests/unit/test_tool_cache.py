"""Unit tests for the read-through tool-result cache (plan 1.2)."""
from __future__ import annotations

from aps.infra import cache


def setup_function(_):
    cache.clear()


def test_second_call_is_a_hit_and_skips_compute():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"result-{calls['n']}"

    first = cache.get_or_call("github_list_issues", {"query": "x"}, compute)
    second = cache.get_or_call("github_list_issues", {"query": "x"}, compute)

    assert first == "result-1"
    assert second == "result-1"          # served from cache, compute ran only once
    assert calls["n"] == 1
    s = cache.stats()
    assert s["hits"] == 1 and s["misses"] == 1


def test_distinct_args_miss_independently():
    seen = []
    cache.get_or_call("hn_search", {"q": "a"}, lambda: seen.append("a") or "a")
    cache.get_or_call("hn_search", {"q": "b"}, lambda: seen.append("b") or "b")
    assert seen == ["a", "b"]
    assert cache.stats()["misses"] == 2


def test_key_is_order_independent():
    cache.get_or_call("t", {"a": 1, "b": 2}, lambda: "v")
    # same args, different dict insertion order → same key → a hit
    cache.get_or_call("t", {"b": 2, "a": 1}, lambda: "SHOULD_NOT_RUN")
    assert cache.stats()["hits"] == 1


def test_clear_resets_entries_and_counters():
    cache.get_or_call("t", {"a": 1}, lambda: "v")
    cache.clear()
    s = cache.stats()
    assert s == {"hits": 0, "misses": 0, "size": 0, "hit_rate": 0.0}


def test_disabled_under_pytest():
    # The hermetic suite must not let the read-through path share state across cases.
    assert cache.enabled() is False


# ── per-TTL buckets (Phase 4/5: long TTL for slow-changing domain/trademark/compliance) ──
def test_ttl_bucket_caches_and_hits():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"r-{calls['n']}"

    a = cache.get_or_call("check_domain_availability", {"d": "x.com"}, compute, ttl=21600)
    b = cache.get_or_call("check_domain_availability", {"d": "x.com"}, compute, ttl=21600)
    assert a == b == "r-1" and calls["n"] == 1
    assert cache.stats()["hits"] == 1


def test_same_key_different_ttl_is_a_separate_bucket():
    # A long-TTL entry must not be served to a default-TTL lookup (different bucket).
    cache.get_or_call("t", {"a": 1}, lambda: "long", ttl=86400)
    cache.get_or_call("t", {"a": 1}, lambda: "default")  # default bucket → its own miss
    s = cache.stats()
    assert s["misses"] == 2 and s["size"] == 2


def test_clear_drops_all_buckets():
    cache.get_or_call("t", {"a": 1}, lambda: "v", ttl=21600)
    cache.get_or_call("t", {"a": 2}, lambda: "v", ttl=86400)
    cache.clear()
    assert cache.stats() == {"hits": 0, "misses": 0, "size": 0, "hit_rate": 0.0}
