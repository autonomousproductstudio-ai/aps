"""Availability tools (Launch Studio Phase 4): RDAP status mapping, trademark links."""
from __future__ import annotations

from aps.infra import http
from aps.tools.availability.check_domain_availability import TOOL as DOMAIN
from aps.tools.availability.search_trademark import TOOL as TM


class _Resp:
    def __init__(self, code):
        self.status_code = code


def test_registry_exposes_availability_namespace():
    from aps.tools.registry import load_registry
    reg = load_registry()
    assert len(reg["availability"]) == 2
    assert sum(len(v) for v in reg.values()) == 69


def test_domain_status_maps_from_rdap_codes(monkeypatch):
    # .com -> 404 (available), .io -> 200 (registered), rest -> 500 (unknown)
    codes = {"habitly.com": 404, "habitly.io": 200}

    def fake_get(url, **kw):
        domain = url.rsplit("/", 1)[-1]
        return _Resp(codes.get(domain, 500))

    monkeypatch.setattr(http, "get", fake_get)
    out = DOMAIN.run(name="Habitly")
    by = {d["domain"]: d["status"] for d in out.payload["domains"]}
    assert by["habitly.com"] == "available"
    assert by["habitly.io"] == "registered"
    assert by["habitly.app"] == "unknown"


def test_domain_all_unknown_falls_back_to_fixture(monkeypatch):
    def boom(url, **kw):
        raise RuntimeError("offline")

    monkeypatch.setattr(http, "get", boom)
    out = DOMAIN.run(name="Habitly")
    assert out.ok                                   # fixture fallback (allow_fixture_fallback)
    assert any(d["status"] == "available" for d in out.payload["domains"])


def test_domain_slug_strips_nonalnum(monkeypatch):
    seen = []
    monkeypatch.setattr(http, "get",
                        lambda url, **kw: seen.append(url) or _Resp(404))
    DOMAIN.run(name="Privacy-First Tracker!")
    assert any("privacyfirsttracker.com" in u for u in seen)


def test_trademark_returns_registry_link_per_jurisdiction():
    india = TM.run(mark="Habitly", jurisdiction="India").payload["trademarks"][0]
    assert "ipindia" in india["search_url"].lower() and india["status"] == "check_required"
    us = TM.run(mark="Habitly", jurisdiction="Delaware, USA").payload["trademarks"][0]
    assert "uspto" in us["search_url"].lower()
    eu = TM.run(mark="Habitly", jurisdiction="European Union").payload["trademarks"][0]
    assert "euipo" in eu["search_url"].lower()


def test_trademark_is_indicative_only():
    tm = TM.run(mark="Habitly", jurisdiction="India").payload["trademarks"][0]
    assert "indicative" in tm["note"].lower()
