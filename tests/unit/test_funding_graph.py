"""Funding graph wiring: flag off = unchanged graph; flag on = parallel branch off execution,
no concurrent-write error, reuses upstream artifacts, existing artifacts still produced."""
from __future__ import annotations

from aps.orchestrator import graph as g
from aps.orchestrator.events import EventBus
from aps.state.models import RunStatus

_ALL = ("research", "prd", "trd", "execution", "pitch", "brand", "legal", "funding")


def _run(monkeypatch, enabled: bool, run_id: str):
    monkeypatch.setattr(g, "USE_STUBS", True)
    monkeypatch.setenv("APS_ENABLE_FUNDING", "true" if enabled else "false")
    bus = EventBus()
    state = g.run_sync("a privacy-first habit tracker", bus, run_id=run_id)
    return state, [e.type for e in bus.history(run_id)]


def _artifact_names(state) -> set:
    return {a for a in _ALL if getattr(state, a, None) is not None}


def test_flag_off_no_funding(monkeypatch):
    state, _ = _run(monkeypatch, enabled=False, run_id="fund_off")
    assert state.funding is None
    assert "funding" not in _artifact_names(state)
    assert state.execution is not None and state.pitch is not None   # vertical intact


def test_flag_on_runs_funding_in_parallel(monkeypatch):
    state, types = _run(monkeypatch, enabled=True, run_id="fund_on")
    assert state.status in (RunStatus.COMPLETE, RunStatus.DEGRADED)   # no InvalidUpdateError
    assert state.funding is not None and state.funding.company_name
    assert len(state.funding.rounds) == 3 and state.funding.deck_slides
    assert {"prd", "trd", "execution", "pitch", "funding"} <= _artifact_names(state)
    # financials model exists (3 years) — reuses upstream execution infra estimate
    assert len(state.funding.financials.get("years", [])) == 3
    assert "artifact_ready" in types


def test_compiled_graph_node_set_reflects_flag(monkeypatch):
    monkeypatch.setenv("APS_ENABLE_FUNDING", "false")
    nodes_off = set(g.build_graph(EventBus(), "n1").get_graph().nodes)
    monkeypatch.setenv("APS_ENABLE_FUNDING", "true")
    nodes_on = set(g.build_graph(EventBus(), "n2").get_graph().nodes)
    assert "funding" not in nodes_off
    assert "funding" in nodes_on
