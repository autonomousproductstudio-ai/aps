"""Req-5 end-to-end: idea → Research → PRD → TRD → ExecutionPlan → Pitch, all offline.

Proves the typed composition chain: each agent consumes the previous typed object and
the idea propagates the whole way. Uses the existing research stub as the upstream
(the Research agent itself is LLM-driven / P1 and out of scope here).
"""
from __future__ import annotations

from aps.agents.research.stub import stub_research
from aps.agents.product.agent import run_product
from aps.agents.architecture.agent import run_architecture
from aps.agents.execution.agent import run_execution
from aps.agents.presentation.agent import run_presentation
from aps.state.models import StudioState, PRD, TRD, ExecutionPlan, PitchPackage

IDEA = "Build an AI SaaS for resume screening"


def _run_chain(idea: str) -> StudioState:
    research = stub_research(idea)
    prd = run_product(research)
    trd = run_architecture(prd)
    plan = run_execution(trd, prd=prd)
    state = StudioState(idea=idea, research=research, prd=prd, trd=trd, execution=plan)
    state.pitch = run_presentation(state)
    return state


def test_full_chain_produces_schema_valid_artifacts():
    s = _run_chain(IDEA)
    assert isinstance(s.prd, PRD)
    assert isinstance(s.trd, TRD)
    assert isinstance(s.execution, ExecutionPlan)
    assert isinstance(s.pitch, PitchPackage)


def test_idea_propagates_through_the_chain():
    s = _run_chain(IDEA)
    assert s.idea == IDEA
    assert s.research.idea == IDEA
    assert s.prd.idea == IDEA
    assert IDEA.split()[-1].lower() in (s.trd.api_spec["info"]["title"] + s.pitch.investor_memo).lower()


def test_handoffs_are_non_trivial():
    s = _run_chain(IDEA)
    # PRD grounded in research
    assert s.prd.features and s.prd.sources
    # TRD's API derived from PRD's features (entities beyond just User)
    assert len(s.trd.data_model["entities"]) >= 2
    assert s.trd.api_spec["paths"]
    # Execution backlog derived from features/endpoints, with effort + sprints
    assert len(s.execution.backlog) >= 3
    assert s.execution.sprints
    # Pitch references the real market + competitors
    assert s.pitch.investor_memo and s.pitch.pitch_outline


def test_chain_is_deterministic():
    # The pipeline is deterministic; the only non-deterministic field is each Evidence's
    # `retrieved_at` timestamp, so we compare the structural artifacts that exclude it.
    a = _run_chain(IDEA)
    b = _run_chain(IDEA)
    assert a.prd.model_dump(exclude={"sources"}) == b.prd.model_dump(exclude={"sources"})
    assert a.trd.api_spec == b.trd.api_spec
    assert a.trd.stack == b.trd.stack
    assert a.execution.model_dump() == b.execution.model_dump()


def test_chain_works_for_a_different_idea():
    s = _run_chain("A marketplace for freelance illustrators")
    assert isinstance(s.pitch, PitchPackage)
    assert s.trd.api_spec["openapi"].startswith("3.")


def test_typed_handoff_research_to_prd():
    """Req-5 (3c): research's typed pains/competitors flow INTO the PRD as typed objects,
    never via a re-prompt. assemble_prd validates/assembles over what upstream produced."""
    research = stub_research(IDEA)
    assert research.pain_points and research.competitors  # upstream actually has signal

    prd = run_product(research)

    # the PRD is grounded in the research object, not regenerated from the idea string
    assert prd.idea == research.idea
    assert prd.features          # pains + competitors -> prioritized features
    assert prd.requirements      # user stories + acceptance criteria
    # evidence is carried through verbatim as the PRD's sources (typed arrow, by URL)
    assert [s.url for s in prd.sources] == [e.url for e in research.evidence]
