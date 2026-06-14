"""Legal graph wiring: flag off = unchanged graph; flag on = parallel branch off architecture,
no concurrent-write error, sees the TRD data model, existing artifacts still produced."""
from __future__ import annotations

from aps.orchestrator import graph as g
from aps.orchestrator.events import EventBus
from aps.state.models import RunStatus

_ALL = ("research", "prd", "trd", "execution", "pitch", "brand", "legal")


def _run(monkeypatch, enabled: bool, run_id: str):
    monkeypatch.setattr(g, "USE_STUBS", True)
    monkeypatch.setenv("APS_ENABLE_LEGAL", "true" if enabled else "false")
    bus = EventBus()
    state = g.run_sync("a privacy-first habit tracker", bus, run_id=run_id)
    return state, [e.type for e in bus.history(run_id)]


def _artifact_names(state) -> set:
    return {a for a in _ALL if getattr(state, a, None) is not None}


def test_flag_off_no_legal(monkeypatch):
    state, _ = _run(monkeypatch, enabled=False, run_id="legal_off")
    assert state.legal is None
    assert "legal" not in _artifact_names(state)
    assert state.prd is not None and state.pitch is not None      # vertical intact


def test_flag_on_runs_legal_in_parallel(monkeypatch):
    state, types = _run(monkeypatch, enabled=True, run_id="legal_on")
    # parallel branch completed without LangGraph InvalidUpdateError (would have raised)
    assert state.status in (RunStatus.COMPLETE, RunStatus.DEGRADED)
    assert state.legal is not None and state.legal.company_name
    assert len(state.legal.documents) == 5
    # existing artifacts still produced alongside legal
    assert {"prd", "trd", "execution", "pitch", "legal"} <= _artifact_names(state)
    # privacy policy is grounded in the TRD data model produced upstream by architecture
    privacy = next(d for d in state.legal.documents if d.kind == "privacy_policy")
    assert "Data we collect" in privacy.body
    # traceable
    assert "artifact_ready" in types


def test_compiled_graph_node_set_reflects_flag(monkeypatch):
    monkeypatch.setenv("APS_ENABLE_LEGAL", "false")
    nodes_off = set(g.build_graph(EventBus(), "n1").get_graph().nodes)
    monkeypatch.setenv("APS_ENABLE_LEGAL", "true")
    nodes_on = set(g.build_graph(EventBus(), "n2").get_graph().nodes)
    assert "legal" not in nodes_off
    assert "legal" in nodes_on
