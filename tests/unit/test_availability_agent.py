"""Availability agent pipeline: AvailabilityReport with/without Brand; renders to Markdown."""
from __future__ import annotations

from aps.agents.availability.agent import run_availability
from aps.state.models import StudioState, BrandPackage, AvailabilityReport
from aps.infra import http
from aps.render import render_artifact


class _Resp:
    def __init__(self, code):
        self.status_code = code


def _stub_rdap(monkeypatch, available_first=True):
    # first candidate (.com) available, the rest registered
    def fake_get(url, **kw):
        return _Resp(404 if url.endswith(".com") else 200)
    monkeypatch.setattr(http, "get", fake_get)


def test_run_availability_uses_brand_name(monkeypatch):
    _stub_rdap(monkeypatch)
    state = StudioState(idea="a privacy-first habit tracker", brand=BrandPackage(name="Habitly"))
    rep = run_availability(state)
    assert isinstance(rep, AvailabilityReport)
    assert rep.company_name == "Habitly"
    assert rep.recommended_domain == "habitly.com"
    assert rep.trademarks and rep.summary


def test_run_availability_idea_only_derives_name(monkeypatch):
    _stub_rdap(monkeypatch)
    rep = run_availability(StudioState(idea="a privacy-first habit tracker"))
    assert rep.company_name                          # derived
    assert rep.domains and len(rep.domains) >= 3


def test_availability_renders_to_markdown(monkeypatch):
    _stub_rdap(monkeypatch)
    rep = run_availability(StudioState(idea="a habit tracker", brand=BrandPackage(name="Habitly")))
    md = render_artifact("availability", rep)
    assert "# Name Availability" in md and "Domains" in md and "Trademark" in md
    assert render_artifact("availability", rep.model_dump()) == md
