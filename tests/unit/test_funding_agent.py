"""Funding agent pipeline: full FundingPackage from Research/PRD/Execution; renders to MD."""
from __future__ import annotations

from aps.agents.funding.agent import run_funding
from aps.state.models import (
    StudioState, ResearchReturn, PRD, Feature, ExecutionPlan, BrandPackage, FundingPackage,
)
from aps.render import render_artifact


def _rich_state() -> StudioState:
    return StudioState(
        idea="a privacy-first habit tracker",
        brand=BrandPackage(name="Habitly"),
        research=ResearchReturn(idea="x", market_size="~$1.2B market"),
        prd=PRD(idea="x", features=[Feature(title="Streak tracking", description="x")],
                mvp_scope="Track habits privately"),
        execution=ExecutionPlan(infra_cost="$400/mo", roadmap="Sprint 1: auth"),
    )


def test_run_funding_full():
    pkg = run_funding(_rich_state())
    assert isinstance(pkg, FundingPackage)
    assert pkg.company_name == "Habitly"
    assert pkg.deck_slides and pkg.financials.get("years")
    assert len(pkg.rounds) == 3 and pkg.use_of_funds
    assert pkg.ask                                  # headline raise set
    # financials grounded in the research TAM + execution infra
    assert pkg.financials["tam"] == 1_200_000_000


def test_run_funding_idea_only_degrades_gracefully():
    pkg = run_funding(StudioState(idea="a habit tracker"))
    assert pkg.company_name and len(pkg.deck_slides) >= 8
    assert pkg.financials["tam"] is None            # no market size → no TAM, still a model
    assert len(pkg.financials["years"]) == 3


def test_run_funding_is_deterministic():
    s = _rich_state()
    assert run_funding(s).model_dump() == run_funding(s).model_dump()


def test_funding_renders_to_markdown():
    pkg = run_funding(_rich_state())
    md = render_artifact("funding", pkg)
    assert "# Funding Pack" in md and "Pitch Deck Outline" in md
    assert "Fundraising Roadmap" in md and "Use of Funds" in md
    assert render_artifact("funding", pkg.model_dump()) == md
