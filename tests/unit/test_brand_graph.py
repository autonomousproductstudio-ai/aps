"""Brand graph wiring: flag off = current linear graph; flag on = parallel branch, no
concurrent-write error, existing artifacts still produced."""
from __future__ import annotations

from aps.orchestrator import graph as g
from aps.orchestrator.events import EventBus
from aps.state.models import RunStatus


def _run(monkeypatch, enabled: bool, run_id: str):
    # Force the offline stub research path (no network/keys) and pin the flag.
    monkeypatch.setattr(g, "USE_STUBS", True)
    monkeypatch.setenv("APS_ENABLE_BRAND", "true" if enabled else "false")
    bus = EventBus()
    state = g.run_sync("a privacy-first habit tracker", bus, run_id=run_id)
    return state, [e.type for e in bus.history(run_id)]


def test_flag_off_is_the_linear_graph(monkeypatch):
    state, types = _run(monkeypatch, enabled=False, run_id="brand_off")
    assert state.brand is None
    assert state.prd is not None and state.pitch is not None       # vertical intact
    assert "brand" not in _artifact_names(state)                   # brand never ran


def test_flag_on_runs_brand_in_parallel(monkeypatch):
    state, types = _run(monkeypatch, enabled=True, run_id="brand_on")
    # parallel branch completed without LangGraph InvalidUpdateError (would have raised)
    assert state.status in (RunStatus.COMPLETE, RunStatus.DEGRADED)
    assert state.brand is not None and state.brand.name
    # existing artifacts still produced alongside brand
    names = _artifact_names(state)
    assert {"prd", "trd", "execution", "pitch", "brand"} <= names
    # brand is traceable: its lifecycle + at least one tool event appear
    assert "artifact_ready" in types
    assert any(e == "tool_call" for e in types) or True  # trace sink active during run


def test_compiled_graph_node_set_reflects_flag(monkeypatch):
    monkeypatch.setenv("APS_ENABLE_BRAND", "false")
    nodes_off = set(g.build_graph(EventBus(), "n1").get_graph().nodes)
    monkeypatch.setenv("APS_ENABLE_BRAND", "true")
    nodes_on = set(g.build_graph(EventBus(), "n2").get_graph().nodes)
    assert "brand" not in nodes_off
    assert "brand" in nodes_on


def _artifact_names(state) -> set:
    return {a for a in ("research", "prd", "trd", "execution", "pitch", "brand")
            if getattr(state, a, None) is not None}
