"""
aps.orchestrator.graph — CEO/orchestrator (LangGraph).

The full vertical: Idea → Research → Product → Architecture → Execution → Presentation.
A node routes to one subagent and collects its TYPED return; the orchestrator holds ONLY
the structured returns in StudioState (Req-3 context strategy). Each node emits lifecycle
Events the API streams over SSE.

Robustness: every node is wrapped so a subagent failure (missing LLM key/dep, a bug)
degrades gracefully — Research falls back to a fixture brief, downstream failures emit an
`error` event and skip — so a run always reaches `run_complete` with whatever it produced.

`APS_USE_STUBS=true` forces the Research fixture (no network/keys), letting the whole graph
run on Day 1; the deterministic downstream agents always run for real.
"""
from __future__ import annotations

import os
import sys

from langgraph.graph import StateGraph, START, END

from aps.state.models import StudioState, RunStatus, Event
from aps.orchestrator.events import EventBus
from aps.orchestrator import cancel
from aps.infra import trace
from aps.infra.llm import preflight_check, has_llm_key

USE_STUBS = os.getenv("APS_USE_STUBS", "false").lower() == "true"
# Research fan-out (Phase 3a): plan sub-topics -> parallel sub-researchers -> merge.
# Default on; set APS_RESEARCH_FANOUT=false to use the single-unit research path.
FANOUT = os.getenv("APS_RESEARCH_FANOUT", "true").lower() == "true"
# Fail fast on an invalid (present-but-broken) LLM key instead of degrading silently.
PREFLIGHT = os.getenv("APS_PREFLIGHT", "true").lower() == "true"
# Phase C: when there's no LLM key, try a deterministic keyless research path (real no-key
# tools) before the labeled stub. Off under pytest so the suite stays hermetic (no live calls).
KEYLESS = (os.getenv("APS_KEYLESS_FALLBACK", "true").lower() == "true"
           and "pytest" not in sys.modules)
# Launch Studio Phase 1: the Brand agent runs as a PARALLEL branch off `product`, fanning
# back in at `presentation`. Default ON; APS_ENABLE_BRAND=false restores the exact linear
# graph. Brand is deterministic (no LLM/network) and faster than the arch→exec chain it runs
# beside, so it adds ~0 wall-clock.
def _brand_enabled() -> bool:
    return os.getenv("APS_ENABLE_BRAND", "true").lower() == "true"


# Launch Studio Phase 2: the Legal agent runs as a PARALLEL branch off `architecture` (so its
# privacy policy can read the TRD data model), terminating at END alongside the
# execution→presentation chain. Default ON; APS_ENABLE_LEGAL=false restores the prior graph.
def _legal_enabled() -> bool:
    return os.getenv("APS_ENABLE_LEGAL", "true").lower() == "true"


# Launch Studio Phase 3: the Funding agent runs as a PARALLEL branch off `execution` (it reuses
# the research market size, PRD features, and the execution infra/roadmap), terminating at END
# alongside `presentation`. Default ON; APS_ENABLE_FUNDING=false restores the prior graph.
def _funding_enabled() -> bool:
    return os.getenv("APS_ENABLE_FUNDING", "true").lower() == "true"


# Launch Studio Phase 4: the Availability agent (domain + trademark) runs as a PARALLEL branch
# off `product` (it needs only the brand name), terminating at END. Default ON; light + heavily
# cached (6h TTL), so even with live RDAP calls it adds ~0 to a warm run. It is the first agent
# that does live network I/O, so — like the keyless-research gate — it is OFF by default under
# pytest (the suite stays hermetic/offline); an explicit APS_ENABLE_TRADEMARK always wins, so the
# availability tests opt in (and stub `http`).
def _availability_enabled() -> bool:
    val = os.getenv("APS_ENABLE_TRADEMARK")
    if val is None:
        return "pytest" not in sys.modules
    return val.lower() == "true"


# Launch Studio Phase 5: the Compliance agent runs as a PARALLEL branch off `architecture` (it
# needs the TRD data model), terminating at END. GATED HARD — default OFF; it only runs when
# APS_ENABLE_COMPLIANCE is explicitly true. The deterministic core needs no key; the live
# guidance is 24h-cached + fixture-fallback. When off, there is NO compliance node.
def _compliance_enabled() -> bool:
    return os.getenv("APS_ENABLE_COMPLIANCE", "false").lower() == "true"


# --------------------------------------------------------------------------- #
# Nodes — one per subagent. Each emits start/artifact/end and returns a typed update.
# --------------------------------------------------------------------------- #
def _research_node(bus: EventBus, run_id: str):
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "research"})
        research = _research(state.idea, bus, run_id)
        _emit(bus, run_id, "artifact_ready", {"name": "research"})
        _emit(bus, run_id, "agent_end", {"agent": "research"})
        n = research.tool_calls if research else 0
        _emit(bus, run_id, "tool_calls_total", {"n": n})
        return {"research": research, "current_agent": "product", "tool_calls": n}
    return node


def _product_node(bus: EventBus, run_id: str):
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "product"})
        from aps.agents.product.agent import run_product
        prd = _safe(bus, run_id, "product", lambda: run_product(state.research))
        # run_product is a real deterministic pipeline (decision D2); the old stub_prd
        # fallback is gone. If it ever fails, _safe already emitted an error — surface the
        # gap honestly (prd stays None) rather than masking it with a fake PRD.
        if prd is not None:
            # Composition proof (Req-5): make the typed handoff visible in the trace —
            # research's pains/competitors flow into the PRD's features/requirements.
            rsr = state.research
            _emit(bus, run_id, "composition", {
                "from": "research", "to": "prd",
                "research.pain_points": len(rsr.pain_points) if rsr else 0,
                "research.competitors": len(rsr.competitors) if rsr else 0,
                "prd.features": len(prd.features),
                "prd.requirements": len(prd.requirements),
            })
            _emit(bus, run_id, "artifact_ready", {"name": "prd"})
        _emit(bus, run_id, "agent_end", {"agent": "product"})
        return {"prd": prd, "current_agent": "architecture"}
    return node


def _architecture_node(bus: EventBus, run_id: str):
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "architecture"})
        from aps.agents.architecture.agent import run_architecture
        trd = _safe(bus, run_id, "architecture", lambda: run_architecture(state.prd))
        _emit(bus, run_id, "artifact_ready", {"name": "trd"})
        _emit(bus, run_id, "agent_end", {"agent": "architecture"})
        return {"trd": trd, "current_agent": "execution"}
    return node


def _execution_node(bus: EventBus, run_id: str):
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "execution"})
        from aps.agents.execution.agent import run_execution
        plan = _safe(bus, run_id, "execution",
                     lambda: run_execution(state.trd, prd=state.prd))
        _emit(bus, run_id, "artifact_ready", {"name": "execution"})
        _emit(bus, run_id, "agent_end", {"agent": "execution"})
        return {"execution": plan, "current_agent": "presentation"}
    return node


def _brand_node(bus: EventBus, run_id: str):
    """Parallel branch (Launch Studio Phase 1): idea/PRD → BrandPackage.

    Returns ONLY {"brand": ...} — it must never write a key another parallel node writes
    (e.g. `current_agent`), or LangGraph raises InvalidUpdateError on the concurrent update.
    The arch/exec branch keeps ownership of `current_agent`. Tool calls stream live via the
    `trace` sink installed in run_sync, so every brand tool emits tool_call/tool_result.
    """
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "brand"})
        from aps.agents.brand.agent import run_brand
        brand = _safe(bus, run_id, "brand", lambda: run_brand(state))
        if brand is not None:
            _emit(bus, run_id, "artifact_ready", {"name": "brand"})
        _emit(bus, run_id, "agent_end", {"agent": "brand"})
        return {"brand": brand}
    return node


def _legal_node(bus: EventBus, run_id: str):
    """Parallel branch (Launch Studio Phase 2): idea/brand/TRD → LegalPackage.

    Returns ONLY {"legal": ...} — like the brand node, it must never write a key another
    parallel node writes (e.g. `current_agent`). Runs after `architecture`, so it can read the
    TRD data model for the privacy policy. Tool calls stream live via the `trace` sink.
    """
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "legal"})
        from aps.agents.legal.agent import run_legal
        legal = _safe(bus, run_id, "legal", lambda: run_legal(state))
        if legal is not None:
            _emit(bus, run_id, "artifact_ready", {"name": "legal"})
        _emit(bus, run_id, "agent_end", {"agent": "legal"})
        return {"legal": legal}
    return node


def _funding_node(bus: EventBus, run_id: str):
    """Parallel branch (Launch Studio Phase 3): Research/PRD/Execution → FundingPackage.

    Returns ONLY {"funding": ...}. Runs after `execution`, so the research market size, PRD
    features, and the execution infra/roadmap are all in state. Tool calls stream live via the
    `trace` sink.
    """
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "funding"})
        from aps.agents.funding.agent import run_funding
        funding = _safe(bus, run_id, "funding", lambda: run_funding(state))
        if funding is not None:
            _emit(bus, run_id, "artifact_ready", {"name": "funding"})
        _emit(bus, run_id, "agent_end", {"agent": "funding"})
        return {"funding": funding}
    return node


def _availability_node(bus: EventBus, run_id: str):
    """Parallel branch (Launch Studio Phase 4): brand name → AvailabilityReport (domain +
    trademark). Live, cached retrieval; returns ONLY {"availability": ...}. Tool calls stream
    live via the `trace` sink.
    """
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "availability"})
        from aps.agents.availability.agent import run_availability
        report = _safe(bus, run_id, "availability", lambda: run_availability(state))
        if report is not None:
            _emit(bus, run_id, "artifact_ready", {"name": "availability"})
        _emit(bus, run_id, "agent_end", {"agent": "availability"})
        return {"availability": report}
    return node


def _compliance_node(bus: EventBus, run_id: str):
    """Parallel branch (Launch Studio Phase 5, gated hard): country + TRD data model →
    ComplianceReport. Deterministic core + cached live citations. Returns ONLY
    {"compliance": ...}. Tool calls stream live via the `trace` sink.
    """
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "compliance"})
        from aps.agents.compliance.agent import run_compliance
        report = _safe(bus, run_id, "compliance", lambda: run_compliance(state))
        if report is not None:
            _emit(bus, run_id, "artifact_ready", {"name": "compliance"})
        _emit(bus, run_id, "agent_end", {"agent": "compliance"})
        return {"compliance": report}
    return node


def _presentation_node(bus: EventBus, run_id: str):
    def node(state: StudioState) -> dict:
        _emit(bus, run_id, "agent_start", {"agent": "presentation"})
        from aps.agents.presentation.agent import run_presentation
        pitch = _safe(bus, run_id, "presentation", lambda: run_presentation(state))
        _emit(bus, run_id, "artifact_ready", {"name": "pitch"})
        _emit(bus, run_id, "agent_end", {"agent": "presentation"})
        return {"pitch": pitch, "current_agent": None}
    return node


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph(bus: EventBus, run_id: str):
    g = StateGraph(StudioState)
    g.add_node("research", _research_node(bus, run_id))
    g.add_node("product", _product_node(bus, run_id))
    g.add_node("architecture", _architecture_node(bus, run_id))
    g.add_node("execution", _execution_node(bus, run_id))
    g.add_node("presentation", _presentation_node(bus, run_id))
    g.add_edge(START, "research")
    g.add_edge("research", "product")
    g.add_edge("product", "architecture")
    g.add_edge("architecture", "execution")
    g.add_edge("execution", "presentation")
    # Launch Studio Phase 1: fan `brand` out from product, running in parallel with the
    # architecture→execution→presentation chain, and terminate it directly at END. Brand is an
    # independent artifact (presentation doesn't consume it), so it does NOT fan back into
    # presentation — that would make the shorter brand branch trigger presentation early and
    # collide with `execution` on the single-writer `current_agent` channel. Sinking brand at
    # END keeps the two branches on disjoint channels (brand writes only `brand`), so there's
    # never a concurrent write. Off ⇒ the exact linear graph above.
    g.add_edge("presentation", END)
    if _brand_enabled():
        g.add_node("brand", _brand_node(bus, run_id))
        g.add_edge("product", "brand")
        g.add_edge("brand", END)
    # Launch Studio Phase 2: fan `legal` out from architecture (it reads the TRD data model for
    # the privacy policy), in parallel with execution→presentation, terminating at END. Like
    # brand, the legal node writes only `{"legal": ...}`, so there's no concurrent write to the
    # single-writer `current_agent` channel. Off ⇒ the graph is unchanged.
    if _legal_enabled():
        g.add_node("legal", _legal_node(bus, run_id))
        g.add_edge("architecture", "legal")
        g.add_edge("legal", END)
    # Launch Studio Phase 3: fan `funding` out from execution (it reuses research market size,
    # PRD features, and the execution infra/roadmap), in parallel with `presentation`,
    # terminating at END. Writes only `{"funding": ...}` → no `current_agent` collision. Off ⇒
    # graph unchanged.
    if _funding_enabled():
        g.add_node("funding", _funding_node(bus, run_id))
        g.add_edge("execution", "funding")
        g.add_edge("funding", END)
    # Launch Studio Phase 4: fan `availability` out from product (it needs only the brand name),
    # in parallel, terminating at END. Writes only `{"availability": ...}` → no `current_agent`
    # collision. Off ⇒ graph unchanged.
    if _availability_enabled():
        g.add_node("availability", _availability_node(bus, run_id))
        g.add_edge("product", "availability")
        g.add_edge("availability", END)
    # Launch Studio Phase 5 (gated hard): fan `compliance` out from architecture (it needs the
    # TRD data model), in parallel, terminating at END. Only added when APS_ENABLE_COMPLIANCE is
    # true. Writes only `{"compliance": ...}` → no `current_agent` collision.
    if _compliance_enabled():
        g.add_node("compliance", _compliance_node(bus, run_id))
        g.add_edge("architecture", "compliance")
        g.add_edge("compliance", END)
    return g.compile()


def run_sync(idea: str, bus: EventBus, run_id: str = "run_cli",
             on_state=None, should_cancel=None, cancel_reason=None) -> StudioState:
    """Run the full graph synchronously, returning the final StudioState.

    `on_state(partial)` (optional) is called with the accumulated state after each node, so a
    caller can publish partial artifacts the moment they're produced (plan 1.6) instead of
    only at `run_complete`. It must not raise; exceptions from it are swallowed.

    `should_cancel()` (optional) is polled at each stage boundary and inside the research loop
    (via a ContextVar) for cooperative cancellation (plan 2.2/2.3); when it trips, the run
    unwinds and returns a CANCELLED state with whatever artifacts were produced.

    `cancel_reason()` (optional) returns a human reason for the cancel ("run exceeded 900s
    deadline", "cancelled by user", …) so the run_cancelled event names WHY, not a bare
    "cancelled". Falls back to "cancelled" when not supplied or empty.
    """
    _emit(bus, run_id, "run_start", {"idea": idea})

    # A2: fail fast on an invalid (present-but-broken) key rather than running all five agents
    # on a silent stub fallback. A genuinely keyless run is allowed through — it degrades
    # loudly (A1). Skipped when stubs are forced; the preflight makes no network call without
    # a key, so the offline suite stays hermetic.
    if not USE_STUBS and PREFLIGHT and has_llm_key():
        ok, err = preflight_check()
        if not ok:
            _emit(bus, run_id, "run_failed", {"error": f"LLM preflight failed: {err}"})
            failed = StudioState(idea=idea, status=RunStatus.FAILED)
            failed.events = bus.history(run_id)
            return failed

    app = build_graph(bus, run_id)
    state = StudioState(idea=idea, status=RunStatus.RUNNING)
    # Install the cancel check for this run's context so the research loop + its copy_context()
    # fan-out workers can poll it (plan 2.2). Reset in finally.
    cancel_token = cancel.set_check(should_cancel) if should_cancel else None
    # Install the per-tool event sink (plan §4) → every tool call streams tool_call/tool_result
    # (with latency) onto this run's bus, including from the parallel fan-out workers.
    sink_token = trace.set_sink(lambda t, d: _emit(bus, run_id, t, d))
    # Stream the accumulated state after each node (plan 1.6) so the caller can expose partial
    # artifacts live; the final snapshot equals what .invoke() would have returned.
    out = None
    cancelled = False
    try:
        for snap in app.stream(state, stream_mode="values"):
            out = snap
            if on_state is not None:
                try:
                    on_state(StudioState(**snap) if isinstance(snap, dict) else snap)
                except Exception:
                    pass
            if should_cancel and should_cancel():   # stage-boundary cancel (downstream agents)
                cancelled = True
                break
    except cancel.RunCancelled:                      # mid-research cancel unwound here
        cancelled = True
    finally:
        trace.reset(sink_token)
        if cancel_token is not None:
            cancel.reset(cancel_token)

    final = (StudioState(**out) if isinstance(out, dict) else out) or state

    if cancelled:
        final.status = RunStatus.CANCELLED
        reason = "cancelled"
        if cancel_reason is not None:
            try:
                reason = cancel_reason() or reason
            except Exception:
                pass
        _emit(bus, run_id, "run_cancelled", {"reason": reason})
        _emit(bus, run_id, "run_complete",
              {"status": final.status.value, "degraded": False, "reason": reason})
        final.events = bus.history(run_id)
        return final

    # A1: a run that fell back to the stub fixture is DEGRADED, not COMPLETE — never let a
    # fixture-backed run masquerade as real, idea-specific output.
    degraded = bool(final.research and final.research.degraded)
    final.status = RunStatus.DEGRADED if degraded else RunStatus.COMPLETE
    reason = final.research.degrade_reason if (degraded and final.research) else None
    if degraded:
        # A dedicated event so the cause is one hop away in the trace (and in meta.json),
        # not buried in the error stream — degradation is loud, never silent.
        _emit(bus, run_id, "run_degraded", {"reason": reason})
    _emit(bus, run_id, "run_complete",
          {"status": final.status.value, "degraded": degraded, "reason": reason})
    final.events = bus.history(run_id)   # carry the full trace for CLI/no-loop consumers
    return final


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _classify_cause(text: str) -> str:
    """Map a raw failure string to a short, stable degrade reason for the artifact/trace."""
    t = (text or "").lower()
    if "401" in t or "unauthorized" in t or "authentication" in t:
        return "llm_auth_401"
    if "429" in t or "rate limit" in t or "too many requests" in t:
        return "rate_limited_429"
    if "no nvidia_api_key" in t or "no gemini key" in t or "no llm key" in t:
        return "no_llm_key"
    if "connection" in t or "timeout" in t or "timed out" in t or "resolve" in t:
        return "network"
    if "no evidence" in t:
        return "no_evidence"
    return f"error: {text[:80]}" if text else "unknown"


def _research(idea: str, bus: EventBus, run_id: str):
    from aps.agents.research.stub import stub_research
    if USE_STUBS:
        return stub_research(idea, reason="use_stubs")
    cause = None
    try:
        on_event = lambda type_, data: _emit(bus, run_id, type_, data)  # noqa: E731
        if FANOUT:
            # Fan-out supervisor: parallel sub-researchers, one typed merged brief.
            from aps.agents.research.supervisor import run_research_fanout
            research = run_research_fanout(idea, on_event=on_event)
        else:
            from aps.agents.research.agent import run_research
            research = run_research(idea)
        if not research.evidence and not research.pain_points:
            raise RuntimeError("research produced no evidence")
        return research
    except Exception as e:  # no key / dep / empty
        cause = str(e)
        _emit(bus, run_id, "error", {"agent": "research", "error": cause[:200]})
    reason = _classify_cause(cause)

    # Phase C: try a deterministic keyless research path (real no-key tools) before the
    # stub — turns "no LLM key" into a genuine grounded brief instead of a fixture. Per the
    # honest-degradation decision, a keyless run is REAL evidence but marked degraded (no LLM
    # orchestration ran) with the reason recorded, so it's never mistaken for a full run.
    if KEYLESS:
        try:
            from aps.agents.research.keyless import keyless_research
            kl = keyless_research(idea)
            if kl.evidence:
                kl.degraded = True
                kl.degrade_reason = f"{reason} (keyless real evidence)"
                _emit(bus, run_id, "research_keyless",
                      {"evidence": len(kl.evidence), "reason": reason,
                       "note": "no LLM key — deterministic no-key retrieval"})
                return kl
        except Exception as e2:
            _emit(bus, run_id, "error",
                  {"agent": "research", "error": f"keyless: {str(e2)[:180]}"})

    # last resort: the labeled stub, carrying WHY (run is marked DEGRADED upstream)
    _emit(bus, run_id, "error", {"agent": "research", "fallback": "stub", "reason": reason})
    return stub_research(idea, reason=reason)


def _safe(bus: EventBus, run_id: str, agent: str, fn):
    """Run a deterministic downstream agent; on failure emit error and return None."""
    try:
        return fn()
    except Exception as e:
        _emit(bus, run_id, "error", {"agent": agent, "error": str(e)[:200]})
        return None


def _emit(bus: EventBus, run_id: str, type_: str, data: dict) -> None:
    bus.publish(run_id, Event(type=type_, data=data))
