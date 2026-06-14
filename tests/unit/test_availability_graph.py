"""Availability graph wiring: flag off = unchanged; flag on = parallel branch off product,
no concurrent-write error, existing artifacts still produced."""
from __future__ import annotations

from aps.orchestrator import graph as g
from aps.orchestrator.events import EventBus
from aps.state.models import RunStatus
from aps.infra import http

_ALL = ("research", "prd", "trd", "execution", "pitch", "brand", "legal", "funding",
        "availability")


class _Resp:
    def __init__(self, code):
        self.status_code = code


def _run(monkeypatch, enabled: bool, run_id: str):
    monkeypatch.setattr(g, "USE_STUBS", True)
    # keep RDAP lookups hermetic/fast — no real network in the suite
    monkeypatch.setattr(http, "get", lambda url, **kw: _Resp(404 if url.endswith(".com") else 200))
    monkeypatch.setenv("APS_ENABLE_TRADEMARK", "true" if enabled else "false")
    bus = EventBus()
    state = g.run_sync("a privacy-first habit tracker", bus, run_id=run_id)
    return state, [e.type for e in bus.history(run_id)]


def _names(state) -> set:
    return {a for a in _ALL if getattr(state, a, None) is not None}


def test_flag_off_no_availability(monkeypatch):
    state, _ = _run(monkeypatch, enabled=False, run_id="av_off")
    assert state.availability is None
    assert "availability" not in _names(state)
    assert state.prd is not None and state.pitch is not None


def test_flag_on_runs_availability_in_parallel(monkeypatch):
    state, types = _run(monkeypatch, enabled=True, run_id="av_on")
    assert state.status in (RunStatus.COMPLETE, RunStatus.DEGRADED)   # no InvalidUpdateError
    assert state.availability is not None and state.availability.company_name
    assert state.availability.recommended_domain.endswith(".com")
    assert {"prd", "trd", "execution", "pitch", "availability"} <= _names(state)
    assert "artifact_ready" in types


def test_compiled_graph_node_set_reflects_flag(monkeypatch):
    monkeypatch.setenv("APS_ENABLE_TRADEMARK", "false")
    nodes_off = set(g.build_graph(EventBus(), "n1").get_graph().nodes)
    monkeypatch.setenv("APS_ENABLE_TRADEMARK", "true")
    nodes_on = set(g.build_graph(EventBus(), "n2").get_graph().nodes)
    assert "availability" not in nodes_off
    assert "availability" in nodes_on
