"""Legal Agent (Launch Studio Phase 2, thin/deterministic).

Consumes the StudioState, emits a LegalPackage of five founder-grade document templates
(privacy policy, ToS, mutual NDA, founders' agreement, employment contract). A deterministic
pipeline over the scoped `legal` tools (ADR-0005) — same shape as the Brand agent — so it adds
~1–2s, runs in a parallel graph branch, and needs no LLM key.

Company facts are pulled from state where available: the company name from the Brand package
(or derived from the idea), the data model from the TRD (so the privacy policy reflects what
the product actually stores). Jurisdiction comes from settings (APS_LEGAL_JURISDICTION,
default India). Everything party-specific is left as a clearly-marked [PLACEHOLDER].
"""
from __future__ import annotations

from aps.state.models import StudioState, LegalPackage, LegalDocument
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS
from aps.config.settings import get_settings
from aps.tools.brand._svg import derive_name
from aps.tools.legal import _legal


def run_legal(state: StudioState) -> LegalPackage:
    AGENT_RUNS.labels(agent="legal").inc()
    t = scoped("legal")

    idea = state.idea
    # Company name: prefer the Brand package's name when Brand ran, else derive from the idea.
    company_name = (state.brand.name if state.brand and state.brand.name
                    else derive_name(idea))
    jurisdiction = get_settings().legal_jurisdiction or "India"
    j = _legal.resolve_jurisdiction(jurisdiction)
    # Data model (for the privacy policy) when the TRD is present; else {} → generic categories.
    data_model = state.trd.data_model if state.trd else {}

    docs_raw = [
        call(t, "generate_privacy_policy", company_name=company_name,
             jurisdiction=jurisdiction, data_model=data_model),
        call(t, "generate_terms_of_service", company_name=company_name,
             jurisdiction=jurisdiction, idea=idea),
        call(t, "generate_nda", company_name=company_name, jurisdiction=jurisdiction),
        call(t, "generate_founders_agreement", company_name=company_name,
             jurisdiction=jurisdiction),
        call(t, "generate_employment_contract", company_name=company_name,
             jurisdiction=jurisdiction),
    ]
    documents = [LegalDocument(**d) for d in docs_raw]

    return LegalPackage(
        company_name=company_name,
        jurisdiction=j["name"],
        governing_law=j["governing_law"],
        disclaimer=_legal.DISCLAIMER,
        documents=documents,
    )
