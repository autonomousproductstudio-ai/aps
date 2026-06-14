"""Compliance Agent (Launch Studio Phase 5 — Core + cached retrieval).

Consumes the StudioState, emits a ComplianceReport. Always builds the **deterministic core**
(regime applicability + checklist from the TRD data model + country), then attaches **real
source citations** from a 24h-cached, fixture-fallback retrieval tool. No LLM key required, so
it never blocks a keyless run; `degraded=True` only when no live guidance came back.

Gated hard: only runs when APS_ENABLE_COMPLIANCE is set (the orchestrator does not add the node
otherwise). Country comes from APS_COMPLIANCE_COUNTRY (else the legal jurisdiction).
"""
from __future__ import annotations

from aps.state.models import StudioState, ComplianceReport
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS
from aps.config.settings import get_settings
from aps.tools.compliance import _compliance


def run_compliance(state: StudioState) -> ComplianceReport:
    AGENT_RUNS.labels(agent="compliance").inc()
    t = scoped("compliance")

    s = get_settings()
    country = s.compliance_country or s.legal_jurisdiction or "India"
    data_model = state.trd.data_model if state.trd else {}

    # Deterministic core — always. Pass the idea too so health/payment regimes are detected
    # even when the auto-generated data model uses generic field names.
    core = call(t, "assess_compliance", country=country, data_model=data_model, idea=state.idea)
    regimes = core["regimes"]
    checklist = core["checklist"]

    # Live citations (cached 24h, fixture fallback). Never raises into the pipeline.
    sources = []
    degraded = True
    note = "Deterministic checklist only — live guidance unavailable."
    try:
        guidance = scoped("compliance")["search_compliance_guidance"].run(
            regimes=[r["name"] for r in regimes])
        sources = guidance.evidence or []
        if guidance.payload and guidance.payload.get("live"):
            degraded = False
            note = ""
    except Exception:
        pass

    n_applicable = sum(1 for r in regimes if r.get("applicable"))
    summary = (f"{country}: {n_applicable} regime(s) apply "
               f"({', '.join(r['name'] for r in regimes[:3])}…); "
               f"{len(checklist)} checklist items. {_compliance.DISCLAIMER}")

    return ComplianceReport(
        country=core["country"],
        regimes=regimes,
        checklist=checklist,
        sources=sources,
        summary=summary,
        degraded=degraded,
        note=note,
    )
