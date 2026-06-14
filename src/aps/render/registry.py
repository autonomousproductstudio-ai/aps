"""artifact name → renderer dispatch (plan.md W1).

`render_artifact(name, obj)` accepts either a typed model or a plain dict (the artifact
store persists JSON), coercing the dict into the right model before rendering. Pure and
deterministic. This is the single entry point the API's `?format=md` path calls.
"""
from __future__ import annotations

from typing import Callable

from aps.state.models import (
    ResearchReturn, PRD, TRD, ExecutionPlan, PitchPackage, BrandPackage, LegalPackage,
    FundingPackage, AvailabilityReport, ComplianceReport,
)
from aps.render import (
    research_md, prd_md, trd_md, execution_md, pitch_md, brand_md, legal_md, funding_md,
    availability_md, compliance_md,
)

# artifact name -> (model type, render fn)
_MODELS = {
    "research": ResearchReturn,
    "prd": PRD,
    "trd": TRD,
    "execution": ExecutionPlan,
    "pitch": PitchPackage,
    "brand": BrandPackage,
    "legal": LegalPackage,
    "funding": FundingPackage,
    "availability": AvailabilityReport,
    "compliance": ComplianceReport,
}

RENDERERS: dict[str, Callable] = {
    "research": research_md.render,
    "prd": prd_md.render,
    "trd": trd_md.render,
    "execution": execution_md.render,
    "pitch": pitch_md.render,
    "brand": brand_md.render,
    "legal": legal_md.render,
    "funding": funding_md.render,
    "availability": availability_md.render,
    "compliance": compliance_md.render,
}


def render_artifact(name: str, obj) -> str:
    """Render an artifact (model or dict) to Markdown. Raises KeyError on unknown name."""
    if name not in RENDERERS:
        raise KeyError(f"no renderer for artifact '{name}'")
    model = _MODELS[name]
    if isinstance(obj, dict):
        obj = model.model_validate(obj)
    return RENDERERS[name](obj)
