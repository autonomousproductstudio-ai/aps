"""Each downstream agent returns its exact typed object, populated from real upstream data."""
from __future__ import annotations

from aps.state.models import PRD, TRD, ExecutionPlan, PitchPackage, StudioState
from aps.agents.product.agent import run_product
from aps.agents.architecture.agent import run_architecture
from aps.agents.execution.agent import run_execution
from aps.agents.presentation.agent import run_presentation


def test_product_agent_returns_populated_prd(rich_research):
    prd = run_product(rich_research)
    assert isinstance(prd, PRD)
    assert prd.idea == rich_research.idea
    assert prd.personas and prd.features and prd.requirements
    assert prd.mvp_scope
    # features trace back to the pains
    assert any("PDF" in f.title or "Parser" in f.title or "parser" in f.title.lower()
               for f in prd.features)
    # top pain (HIGH) yields a Must feature
    assert any(f.priority == "Must" for f in prd.features)
    # sources carried from research evidence
    assert prd.sources


def test_architecture_agent_returns_trd_with_valid_openapi(rich_research):
    prd = run_product(rich_research)
    trd = run_architecture(prd)
    assert isinstance(trd, TRD)
    assert trd.api_spec.get("openapi", "").startswith("3.")
    assert trd.api_spec.get("paths")
    assert "entities" in trd.data_model and "User" in trd.data_model["entities"]
    assert trd.stack and trd.scale_estimate


def test_execution_agent_returns_plan(rich_research):
    prd = run_product(rich_research)
    trd = run_architecture(prd)
    plan = run_execution(trd, prd=prd)
    assert isinstance(plan, ExecutionPlan)
    assert plan.backlog and plan.sprints
    assert plan.roadmap and plan.infra_cost
    assert all("points" in item for item in plan.backlog)


def test_presentation_agent_returns_pitch(rich_research):
    prd = run_product(rich_research)
    trd = run_architecture(prd)
    plan = run_execution(trd, prd=prd)
    state = StudioState(idea=rich_research.idea, research=rich_research,
                        prd=prd, trd=trd, execution=plan)
    pitch = run_presentation(state)
    assert isinstance(pitch, PitchPackage)
    assert pitch.pitch_outline and pitch.demo_script and pitch.investor_memo
    assert "JUDGE BRIEF" in pitch.investor_memo  # judge brief folded in (decision.md D4)


def test_product_agent_handles_empty_research():
    from aps.state.models import ResearchReturn
    prd = run_product(ResearchReturn(idea="bare idea"))
    assert isinstance(prd, PRD) and prd.idea == "bare idea"
    assert prd.personas  # always at least one persona
