"""aps.tools.base — the Tool contract every P2 tool implements.

A tool is a fine-grained REAL operation (ADR-0004). Retrieval tools hit a live
source and return normalized Evidence; analysis tools operate on retrieved data.
Artifact *writing* is the agent's job, never a tool.
"""
from __future__ import annotations
import time
from typing import Protocol, runtime_checkable
from pydantic import BaseModel
from aps.state.models import ToolResult
from aps.infra.metrics import record_tool_call
from aps.infra.logging import get_logger
from aps.infra import trace

_LOG = get_logger("aps.tools")


class Tool(Protocol):
    name: str                       # snake_case; what the model emits
    namespace: str                  # retrieval | analysis | product | architecture | execution | presentation
    description: str                # the model reads THIS to choose — write it well
    args_schema: type[BaseModel]    # typed inputs

    def run(self, **kwargs) -> ToolResult: ...


@runtime_checkable
class ToolImpl(Protocol):
    name: str
    namespace: str
    description: str
    args_schema: type[BaseModel]
    def run(self, **kwargs) -> ToolResult: ...


class BaseTool:
    """Optional convenience base. Set the four class attrs; implement _run()."""
    name: str = ""
    namespace: str = ""
    description: str = ""
    args_schema: type[BaseModel]
    # Read-through cache TTL in seconds. None ⇒ not cached unless namespace == "retrieval"
    # (which uses the default TTL). Slow-changing live tools (domain/trademark, compliance —
    # plan Phase 4/5) set a long TTL so repeat runs are near-free.
    cache_ttl: int | None = None

    def run(self, **kwargs) -> ToolResult:
        # Central instrumentation: every tool call is counted + logged here, so
        # observability is wired once rather than in 52 tools (NFR-3/§9). Cached hits are
        # still counted — the metric reflects what the model asked for, not cache state.
        try:
            args = self.args_schema(**kwargs)
        except Exception as e:  # bad args -> typed error, not a crash
            record_tool_call(self.name, self.namespace, ok=False)
            return ToolResult(ok=False, error=f"bad_args: {e}")
        # Live tool stream + per-tool latency (plan §4): emit start/end through the run's sink
        # (a no-op outside a run). The end event carries elapsed ms, ok, and evidence count.
        trace.emit("tool_call", {"tool": self.name, "namespace": self.namespace})
        t0 = time.perf_counter()
        result = self._cached_or_run(args, kwargs)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        record_tool_call(self.name, self.namespace, ok=result.ok)
        trace.emit("tool_result", {"tool": self.name, "namespace": self.namespace,
                                   "ok": result.ok, "evidence": len(result.evidence), "ms": ms})
        _LOG.debug("tool_call", tool=self.name, namespace=self.namespace,
                   ok=result.ok, evidence=len(result.evidence), ms=ms)
        return result

    def _cached_or_run(self, args: BaseModel, kwargs: dict) -> ToolResult:
        """Read-through cache for retrieval/live tools (plan 1.2 + Phase 4/5); compute directly
        otherwise.

        Cached when the tool is a `retrieval` tool (default TTL) OR declares a `cache_ttl`
        (e.g. the domain/trademark/compliance live tools, which want a long TTL on slow-changing
        data). Analysis tools are deterministic, cheap, and take `list[Evidence]` (not usefully
        hashable), so they stay uncached. A cache hit is returned as a DEEP COPY so a downstream
        in-place mutation (fixture title stamping, compression filtering) on one run can never
        corrupt the shared cached entry.
        """
        from aps.infra import cache
        ttl = getattr(self, "cache_ttl", None)
        cacheable = self.namespace == "retrieval" or ttl is not None
        if not (cache.enabled() and cacheable):
            return self._run(args)
        result = cache.get_or_call(self.name, kwargs, lambda: self._run(args), ttl=ttl)
        return result.model_copy(deep=True) if hasattr(result, "model_copy") else result

    def _run(self, args: BaseModel) -> ToolResult:  # P2 implements per tool
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Shared helpers (used by every concrete tool)
# --------------------------------------------------------------------------- #
USER_AGENT = "autonomous-product-studio/0.1 (research agent; +https://github.com)"
DEFAULT_TIMEOUT = 15


def fixture_or_error(msg: str, evidence=None, payload=None) -> ToolResult:
    """Demo resilience (TRD §7): if fixture fallback is allowed, return recorded
    sample data so a judge can always run the tool; otherwise surface a typed error.

    `evidence` is a list[Evidence] to hand back when no key / no network / bad dep.
    """
    from aps.config.settings import get_settings

    if get_settings().allow_fixture_fallback:
        evs = list(evidence or [])
        # Stamp every fixture so compression can exclude it from a real brief — placeholder
        # data must never ground real research (this is what let resume/ATS fixtures bleed
        # into unrelated ideas when a keyed tool fell back).
        for e in evs:
            title = e.title or ""
            if not title.startswith("[fixture]"):
                e.title = ("[fixture] " + title).strip()
        # W4: log loudly that this is fixture data, not live — a judge inspecting logs (or
        # the [fixture] title stamps) can always tell a degraded source from a real one.
        _LOG.warning("tool_fixture_fallback", reason=str(msg)[:160], items=len(evs))
        return ToolResult(ok=True, payload=payload, evidence=evs)
    return ToolResult(ok=False, error=msg)
