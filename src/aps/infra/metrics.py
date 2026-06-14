"""Prometheus metrics (TRD §9). NOT a counted tool — platform capability.

Exposes process-wide counters/histograms and `setup_metrics(app)` to mount `/metrics`
on a FastAPI app. When prometheus_client is absent, every metric becomes a no-op shim
so callers (`TOOL_CALLS.labels(...).inc()`) work unchanged and nothing imports-fails.
"""
from __future__ import annotations

from contextlib import contextmanager

try:  # optional dependency
    from prometheus_client import Counter, Histogram, make_asgi_app
    _HAVE_PROM = True
except Exception:  # pragma: no cover - exercised only when dep missing
    _HAVE_PROM = False


class _NoopMetric:
    """Stand-in so metric calls are safe when prometheus_client isn't installed."""
    def labels(self, *_a, **_k):
        return self
    def inc(self, *_a, **_k):
        return None
    def observe(self, *_a, **_k):
        return None
    def time(self):
        return _noop_timer()


@contextmanager
def _noop_timer():
    yield


if _HAVE_PROM:
    TOOL_CALLS = Counter("aps_tool_calls_total", "Tool invocations", ["tool", "namespace"])
    TOOL_ERRORS = Counter("aps_tool_errors_total", "Tool failures", ["tool", "namespace"])
    AGENT_RUNS = Counter("aps_agent_runs_total", "Agent invocations", ["agent"])
    AGENT_LATENCY = Histogram("aps_agent_latency_seconds", "Agent run latency", ["agent"])
    LLM_CALLS = Counter("aps_llm_calls_total", "LLM calls that succeeded", ["provider"])
    LLM_FAILOVERS = Counter("aps_llm_failover_total", "LLM failovers to the next provider", ["provider"])
else:
    TOOL_CALLS = _NoopMetric()
    TOOL_ERRORS = _NoopMetric()
    AGENT_RUNS = _NoopMetric()
    AGENT_LATENCY = _NoopMetric()
    LLM_CALLS = _NoopMetric()
    LLM_FAILOVERS = _NoopMetric()


def record_tool_call(tool: str, namespace: str, ok: bool) -> None:
    """Convenience used by the tool layer to count a call and any error."""
    TOOL_CALLS.labels(tool=tool, namespace=namespace).inc()
    if not ok:
        TOOL_ERRORS.labels(tool=tool, namespace=namespace).inc()


def record_llm_call(provider: str, ok: bool) -> None:
    """Count an LLM provider call (success) or a failover away from it (multipleAPIplan P5)."""
    if ok:
        LLM_CALLS.labels(provider=provider).inc()
    else:
        LLM_FAILOVERS.labels(provider=provider).inc()


def setup_metrics(app) -> None:
    """Mount Prometheus `/metrics` on a FastAPI/Starlette app (no-op if dep absent)."""
    if not _HAVE_PROM:
        return
    app.mount("/metrics", make_asgi_app())
