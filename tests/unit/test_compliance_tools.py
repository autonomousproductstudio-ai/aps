"""Compliance tools (Launch Studio Phase 5): deterministic applicability + cached guidance."""
from __future__ import annotations

from aps.infra import http
from aps.tools.compliance.assess_compliance import TOOL as ASSESS
from aps.tools.compliance.search_compliance_guidance import TOOL as GUIDANCE

_HEALTH_DM = {"entities": {"Vitals": {"fields": {"heart_rate": "int", "email": "string"}}}}
_PAY_DM = {"entities": {"Order": {"fields": {"card_number": "string", "amount": "int"}}}}


class _Resp:
    def __init__(self, code):
        self.status_code = code


def test_registry_exposes_compliance_namespace():
    from aps.tools.registry import load_registry
    reg = load_registry()
    assert len(reg["compliance"]) == 2
    assert sum(len(v) for v in reg.values()) == 69


def test_privacy_regime_adapts_to_country():
    india = ASSESS.run(country="India", data_model={}).payload
    assert any("DPDP" in r["name"] for r in india["regimes"])
    eu = ASSESS.run(country="European Union", data_model={}).payload
    assert any("GDPR" in r["name"] for r in eu["regimes"])
    us = ASSESS.run(country="Delaware, USA", data_model={}).payload
    assert any("CCPA" in r["name"] for r in us["regimes"])


def test_soc2_baseline_always_present():
    p = ASSESS.run(country="India", data_model={}).payload
    assert any("SOC 2" in r["name"] for r in p["regimes"])
    assert p["checklist"]                                   # always a non-empty checklist


def test_health_data_triggers_health_regime():
    p = ASSESS.run(country="India", data_model=_HEALTH_DM).payload
    assert any("Health" in r["name"] for r in p["regimes"])


def test_payment_data_triggers_pci():
    p = ASSESS.run(country="India", data_model=_PAY_DM).payload
    assert any("PCI" in r["name"] for r in p["regimes"])
    assert any("PCI" in c["regime"] for c in p["checklist"])


def test_idea_text_triggers_health_and_payment():
    # the auto-generated data model uses generic fields; the idea text is the signal
    p = ASSESS.run(country="India", data_model={},
                   idea="a health tracker that stores vitals and card payments").payload
    names = " ".join(r["name"] for r in p["regimes"])
    assert "Health" in names and "PCI" in names


def test_assess_is_deterministic():
    a = ASSESS.run(country="India", data_model=_HEALTH_DM).payload
    b = ASSESS.run(country="India", data_model=_HEALTH_DM).payload
    assert a == b


def test_guidance_returns_citations_live(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, **kw: _Resp(200))
    out = GUIDANCE.run(regimes=["DPDP Act (India)", "SOC 2 / ISO 27001"])
    assert out.ok and out.payload["live"] is True
    assert len(out.evidence) >= 2 and all(e.url.startswith("http") for e in out.evidence)


def test_guidance_fixture_fallback_offline(monkeypatch):
    def boom(url, **kw):
        raise RuntimeError("offline")
    monkeypatch.setattr(http, "get", boom)
    out = GUIDANCE.run(regimes=["DPDP Act (India)"])
    assert out.ok                                          # fixture fallback (still labelled links)
    assert out.evidence
