"""Legal tools (Launch Studio Phase 2): valid documents, disclaimer, placeholders,
determinism, jurisdiction adaptivity, data-model-grounded privacy policy."""
from __future__ import annotations

from aps.tools.legal.generate_privacy_policy import TOOL as PRIVACY
from aps.tools.legal.generate_terms_of_service import TOOL as TOS
from aps.tools.legal.generate_nda import TOOL as NDA
from aps.tools.legal.generate_founders_agreement import TOOL as FOUNDERS
from aps.tools.legal.generate_employment_contract import TOOL as EMPLOYMENT
from aps.tools.legal import _legal

ALL = [PRIVACY, TOS, NDA, FOUNDERS, EMPLOYMENT]
DM = {"entities": {"User": {"fields": {"email": "string", "owner_id": "uuid",
                                        "created_at": "datetime"}}}}


def test_registry_exposes_legal_namespace():
    from aps.tools.registry import load_registry
    reg = load_registry()
    assert len(reg["legal"]) == 5
    assert sum(len(v) for v in reg.values()) == 69


def test_every_doc_has_disclaimer_company_and_kind():
    for tool in ALL:
        out = tool.run(company_name="Habitly", jurisdiction="India")
        assert out.ok
        d = out.payload
        assert d["kind"] and d["title"]
        assert "NOT LEGAL ADVICE" in d["body"]
        assert "Habitly" in d["body"]
        assert isinstance(d["placeholders"], list) and d["placeholders"]


def test_documents_are_deterministic():
    for tool in ALL:
        a = tool.run(company_name="Habitly", jurisdiction="India").payload["body"]
        b = tool.run(company_name="Habitly", jurisdiction="India").payload["body"]
        assert a == b


def test_privacy_policy_reflects_data_model_and_dpdp():
    out = PRIVACY.run(company_name="Habitly", jurisdiction="India", data_model=DM).payload
    assert "DPDP" in out["body"] or "Digital Personal Data Protection" in out["body"]
    assert "Email address" in out["body"]          # from the data model
    assert "Usage and activity data" in out["body"]


def test_privacy_policy_jurisdiction_adaptive():
    eu = PRIVACY.run(company_name="Habitly", jurisdiction="European Union", data_model=DM).payload
    assert "GDPR" in eu["body"]
    us = PRIVACY.run(company_name="Habitly", jurisdiction="Delaware, USA", data_model=DM).payload
    assert "CCPA" in us["body"]


def test_employment_framing_adapts_to_jurisdiction():
    india = EMPLOYMENT.run(company_name="Habitly", jurisdiction="India").payload["body"]
    us = EMPLOYMENT.run(company_name="Habitly", jurisdiction="Delaware, USA").payload["body"]
    assert "notice" in india.lower() and "at-will" not in india.lower()
    assert "at-will" in us.lower()


def test_founders_agreement_lists_each_founder():
    out = FOUNDERS.run(company_name="Habitly", jurisdiction="India", num_founders=3).payload
    assert "[FOUNDER 1 NAME]" in out["body"] and "[FOUNDER 3 NAME]" in out["body"]
    assert "vest" in out["body"].lower() and "cliff" in out["body"].lower()


def test_missing_company_surfaces_placeholder():
    out = NDA.run(jurisdiction="India").payload          # no company_name
    assert "[COMPANY NAME]" in out["body"]
    assert "[COMPANY NAME]" in out["placeholders"]


def test_data_categories_fallback_when_empty():
    assert _legal.data_categories({}) == _legal.data_categories(None)
    assert "Email address" in _legal.data_categories({})   # sensible generic set
