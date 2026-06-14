"""Orchestrator: the real LangGraph pipeline runs end-to-end offline + emits events.

Research has no LLM key here, so the research node degrades to the fixture brief; the
deterministic downstream agents run for real. The whole graph still reaches run_complete.
"""
from __future__ import annotations

import asyncio

from aps.orchestrator.events import EventBus
from aps.orchestrator.graph import run_sync
from aps.state.models import RunStatus, PRD, TRD, ExecutionPlan, PitchPackage, Event

IDEA = "Build an AI SaaS for resume screening"


def _run():
    bus = EventBus()
    return bus, run_sync(IDEA, bus, run_id="t_run")


def test_full_pipeline_produces_all_artifacts():
    _, state = _run()
    # No LLM key in the test env -> research degrades to the fixture, so the run is honestly
    # DEGRADED (not COMPLETE) but still produces all five downstream artifacts.
    assert state.status == RunStatus.DEGRADED
    assert state.idea == IDEA
    assert isinstance(state.prd, PRD)
    assert isinstance(state.trd, TRD)
    assert isinstance(state.execution, ExecutionPlan)
    assert isinstance(state.pitch, PitchPackage)
    assert state.research is not None
    # real downstream work
    assert state.trd.api_spec.get("openapi", "").startswith("3.")
    assert state.execution.backlog


def test_event_lifecycle_is_complete_and_ordered():
    bus, state = _run()
    history = bus.history("t_run")
    types = [e.type for e in history]
    assert types[0] == "run_start"
    assert types[-1] == "run_complete"
    # The core 5-agent spine always runs; the Launch Studio parallel branches (brand/legal/
    # funding, default on) add more, so assert the spine is present rather than a fixed count.
    starts = [e.data.get("agent") for e in history if e.type == "agent_start"]
    ends = [e.data.get("agent") for e in history if e.type == "agent_end"]
    for agent in ("research", "product", "architecture", "execution", "presentation"):
        assert agent in starts and agent in ends
    # every agent that starts also ends — a balanced lifecycle
    assert sorted(starts) == sorted(ends)
    # the lifecycle is bracketed by run_start … run_complete
    assert types.index("run_start") < types.index("agent_start") < types.index("run_complete")
    # state carries the full trace for no-loop consumers
    assert state.events and len(state.events) == len(history)


def test_research_degrades_to_stub_without_keys():
    bus, state = _run()
    errors = [e for e in bus.history("t_run")
              if e.type == "error" and e.data.get("agent") == "research"]
    # no LLM key/dep here -> the fan-out emits informative "no evidence" diagnostics, then
    # the orchestrator records exactly one graceful stub fallback; the run still succeeds.
    fallbacks = [e for e in errors if e.data.get("fallback") == "stub"]
    assert len(fallbacks) == 1
    assert state.research.idea == IDEA


def test_eventbus_history_and_replay():
    bus = EventBus()
    bus.publish("r", Event(type="agent_start", data={"a": 1}))
    bus.publish("r", Event(type="run_complete", data={}))
    assert [e.type for e in bus.history("r")] == ["agent_start", "run_complete"]
    assert bus.is_complete("r") is True

    # a late subscriber still receives the full history via replay
    async def drain():
        q = bus.subscribe("r")
        return [q.get_nowait().type for _ in range(q.qsize())]

    assert asyncio.run(drain()) == ["agent_start", "run_complete"]


def test_two_runs_are_isolated():
    bus = EventBus()
    run_sync("idea one", bus, run_id="a")
    run_sync("idea two", bus, run_id="b")
    assert bus.history("a") and bus.history("b")
    assert all(e.type != "run_start" or e.data["idea"] == "idea one" for e in bus.history("a"))
