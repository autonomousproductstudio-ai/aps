"""Infra works whether or not the optional deps (structlog/tenacity/prometheus) exist."""
from __future__ import annotations


import pytest

from aps.infra.logging import configure_logging, get_logger
from aps.infra.retry import with_retry
from aps.infra.metrics import record_tool_call, setup_metrics, TOOL_CALLS
from aps.infra.rate_limiter import RateLimiter


def test_logging_configures_and_logs():
    configure_logging()
    log = get_logger("test")
    log.info("hello", k=1)  # must not raise on either backend


def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    @with_retry(attempts=3, base_delay=0.001)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_reraises_after_exhausting_attempts():
    calls = {"n": 0}

    @with_retry(attempts=2, base_delay=0.001)
    def always_fail():
        calls["n"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        always_fail()
    assert calls["n"] == 2


def test_retry_bare_decorator_form():
    @with_retry
    def ok():
        return 42

    assert ok() == 42


def test_metrics_record_is_safe():
    # no-op shim or real prometheus — either way these must not raise
    record_tool_call("web_search", "retrieval", ok=True)
    record_tool_call("web_search", "retrieval", ok=False)
    TOOL_CALLS.labels(tool="x", namespace="y").inc()


def test_setup_metrics_noop_without_app():
    class _App:
        def mount(self, *_a, **_k):
            self.mounted = True

    app = _App()
    setup_metrics(app)  # mounts if prometheus present, no-op otherwise; never raises


def test_rate_limiter_allows_burst_then_throttles():
    rl = RateLimiter(rpm=6000)  # 100/sec -> tiny waits, fast test
    waits = [rl.acquire("github", block=False) for _ in range(10)]
    assert waits[0] == 0.0          # first token always free
    assert all(w >= 0 for w in waits)


def test_rate_limiter_isolates_sources():
    rl = RateLimiter(rpm=60)
    rl.configure("slow", rpm=60)
    # different sources draw from different buckets
    assert rl.acquire("a", block=False) == 0.0
    assert rl.acquire("b", block=False) == 0.0
