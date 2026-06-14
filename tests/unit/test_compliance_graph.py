"""Compliance graph wiring: gated hard (default OFF). When enabled, parallel off architecture,
no concurrent-write error, sees the TRD data model, existing artifacts still produced."""
from __future__ import annotations

from aps.infra import http
from aps.orchestrator import graph as g
from aps.orchestrator.events import EventBus
from aps.state.models import RunStatus

_ALL = ("research", "prd", "trd", "execution", "pitch", "brand", "legal", "funding",
        "availability", "compliance")


class _Resp:
    def __init__(self, code):
        self.status_code = code


def _run(monkeypatch, enabled, run_id):
    monkeypatch.setattr(g, "USE_STUBS", True)
    monkeypatch.setattr(http, "get", lambda url, **kw: _Resp(200))   # hermetic guidance fetch
    if enabled is None:
        monkeypatch.delenv("APS_ENABLE_COMPLIANCE", raising=False)
    else:
        monkeypatch.setenv("APS_ENABLE_COMPLIANCE", "true" if enabled else "false")
    bus = EventBus()
    state = g.run_sync("a health tracker that stores vitals", bus, run_id=run_id)
    return state, [e.type for e in bus.history(run_id)]


def _names(state):
    return {a for a in _ALL if getattr(state, a, None) is not None}


def test_default_off_no_compliance(monkeypatch):
    # gated hard: with no env set, compliance must NOT run
    state, _ = _run(monkeypatch, enabled=None, run_id="cmp_default")
    assert state.compliance is None
    assert "compliance" not in _names(state)


def test_explicit_off_no_compliance(monkeypatch):
    state, _ = _run(monkeypatch, enabled=False, run_id="cmp_off")
    assert state.compliance is None


def test_enabled_runs_compliance_in_parallel(monkeypatch):
    state, types = _run(monkeypatch, enabled=True, run_id="cmp_on")
    assert state.status in (RunStatus.COMPLETE, RunStatus.DEGRADED)   # no InvalidUpdateError
    assert state.compliance is not None and state.compliance.regimes
    assert {"prd", "trd", "execution", "pitch", "compliance"} <= _names(state)
    assert "artifact_ready" in types


def test_compiled_graph_node_set_reflects_flag(monkeypatch):
    monkeypatch.delenv("APS_ENABLE_COMPLIANCE", raising=False)
    nodes_default = set(g.build_graph(EventBus(), "n0").get_graph().nodes)
    monkeypatch.setenv("APS_ENABLE_COMPLIANCE", "true")
    nodes_on = set(g.build_graph(EventBus(), "n1").get_graph().nodes)
    assert "compliance" not in nodes_default          # default OFF
    assert "compliance" in nodes_on
