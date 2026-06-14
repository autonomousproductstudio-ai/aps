"""Legal agent pipeline: full LegalPackage with/without TRD and Brand; renders to Markdown."""
from __future__ import annotations

from aps.agents.legal.agent import run_legal
from aps.state.models import (
    StudioState, TRD, BrandPackage, LegalPackage,
)
from aps.render import render_artifact

DM = {"entities": {"User": {"fields": {"email": "string", "created_at": "datetime"}}}}


def test_run_legal_idea_only():
    pkg = run_legal(StudioState(idea="a privacy-first habit tracker"))
    assert isinstance(pkg, LegalPackage)
    assert pkg.company_name and pkg.jurisdiction and pkg.governing_law
    assert "NOT LEGAL ADVICE" in pkg.disclaimer
    kinds = {d.kind for d in pkg.documents}
    assert kinds == {"privacy_policy", "tos", "nda", "founders_agreement", "employment"}


def test_run_legal_uses_brand_name_and_trd_data_model():
    state = StudioState(
        idea="a privacy-first habit tracker",
        brand=BrandPackage(name="Habitly"),
        trd=TRD(data_model=DM),
    )
    pkg = run_legal(state)
    assert pkg.company_name == "Habitly"
    privacy = next(d for d in pkg.documents if d.kind == "privacy_policy")
    assert "Email address" in privacy.body          # came from the TRD data model


def test_run_legal_is_deterministic():
    state = StudioState(idea="AI-powered accounting for SMEs")
    assert run_legal(state).model_dump() == run_legal(state).model_dump()


def test_legal_renders_to_markdown():
    pkg = run_legal(StudioState(idea="a privacy-first habit tracker"))
    md = render_artifact("legal", pkg)
    assert "# Legal Documents" in md and "Placeholders to complete" in md
    # dict path (artifact-store read-through) matches the model path
    assert render_artifact("legal", pkg.model_dump()) == md
