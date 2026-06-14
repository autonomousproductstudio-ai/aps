"""Architecture Agent (P2, thin-but-real). Consumes PRD, emits a TRD with real OpenAPI.

Deterministic pipeline over the scoped architecture tools (ADR-0005): data model →
OpenAPI contract → scale estimate → tech stack → component design → assemble. The
OpenAPI document from `design_api_contract` is genuinely valid (the must-be-real output,
per MEMO). `assemble_trd` validates the parts into the TRD (ADR-0004).
"""
from __future__ import annotations

from aps.state.models import PRD, TRD
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS


def run_architecture(prd: PRD) -> TRD:
    AGENT_RUNS.labels(agent="architecture").inc()
    t = scoped("architecture")

    data_model = call(t, "design_data_model",
                      idea=prd.idea, features=prd.features, personas=prd.personas)
    api_spec = call(t, "design_api_contract", data_model=data_model, idea=prd.idea)
    scale = call(t, "estimate_scale",
                 idea=prd.idea, features=prd.features, personas=prd.personas)
    stack = call(t, "choose_tech_stack",
                 requirements=prd.requirements, scale_estimate=scale)
    architecture = call(t, "design_architecture", stack=stack, data_model=data_model)

    # carry the component design alongside the entities (TRD.data_model is free-form)
    full_model = {**data_model, "architecture": architecture}

    trd: TRD = call(t, "assemble_trd",
                    data_model=full_model, api_spec=api_spec,
                    stack=stack, scale_estimate=scale)
    return trd
