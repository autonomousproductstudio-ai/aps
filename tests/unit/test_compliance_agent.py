"""Compliance agent pipeline: deterministic core always; live citations when reachable."""
from __future__ import annotations

from aps.infra import http
from aps.agents.compliance.agent import run_compliance
from aps.state.models import StudioState, TRD, ComplianceReport
from aps.render import render_artifact

_HEALTH_DM = {"entities": {"Vitals": {"fields": {"heart_rate": "int", "email": "string"}}}}


class _Resp:
    def __init__(self, code):
        self.status_code = code


def test_core_built_with_live_citations(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, **kw: _Resp(200))
    state = StudioState(idea="a health tracker", trd=TRD(data_model=_HEALTH_DM))
    rep = run_compliance(state)
    assert isinstance(rep, ComplianceReport)
    assert rep.regimes and rep.checklist and rep.country
    assert any("Health" in r["name"] for r in rep.regimes)   # health data detected from TRD
    assert rep.degraded is False and rep.sources              # live guidance attached


def test_degrades_when_guidance_offline(monkeypatch):
    def boom(url, **kw):
        raise RuntimeError("offline")
    monkeypatch.setattr(http, "get", boom)
    rep = run_compliance(StudioState(idea="x", trd=TRD(data_model={})))
    # the deterministic checklist still stands; degraded flags the missing live evidence
    assert rep.checklist
    assert rep.degraded is True and rep.note


def test_renders_to_markdown(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, **kw: _Resp(200))
    rep = run_compliance(StudioState(idea="x", trd=TRD(data_model=_HEALTH_DM)))
    md = render_artifact("compliance", rep)
    assert "# Compliance" in md and "Applicable Regimes" in md and "Checklist" in md
    assert render_artifact("compliance", rep.model_dump()) == md
