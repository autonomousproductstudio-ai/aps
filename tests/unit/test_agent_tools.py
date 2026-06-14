"""Product / Architecture / Execution / Presentation tools: shapes + OpenAPI validity."""
from __future__ import annotations

from aps.state.models import PainPoint, Competitor, Persona, Feature, Severity, PRD, TRD
from aps.tools.product import (
    generate_personas, generate_user_stories, prioritize_features,
    define_mvp_scope, acceptance_criteria, assemble_prd,
)
from aps.tools.architecture import (
    design_data_model, design_api_contract, choose_tech_stack,
    estimate_scale, design_architecture, assemble_trd,
)
from aps.tools.execution import (
    plan_repo_structure, generate_backlog, estimate_effort,
    plan_sprints, generate_roadmap, estimate_infra_cost,
)
from aps.tools.presentation import (
    generate_pitch_outline, generate_demo_script,
    generate_investor_memo, generate_judge_brief,
)


PAINS = [PainPoint(text="parser drops PDFs", severity=Severity.HIGH),
         PainPoint(text="matching misses candidates", severity=Severity.MED)]


# ---- product ----------------------------------------------------------------
def test_personas_from_pains():
    out = generate_personas.TOOL.run(idea="x", pain_points=PAINS)
    assert out.ok and out.payload and isinstance(out.payload[0], Persona)
    assert out.payload[0].frustrations


def test_persona_goals_are_clean_capabilities_not_raw_pain():
    # goals = the positive inverse (a capability), NOT a "Resolve: <raw complaint>" paste
    pains = [PainPoint(text="It is unusable", severity=Severity.HIGH),
             PainPoint(text="no way to bulk delete", severity=Severity.MED)]
    personas = generate_personas.TOOL.run(idea="x", pain_points=pains).payload
    all_goals = [g for p in personas for g in p.goals]
    assert all_goals
    assert not any(g.startswith("Resolve:") for g in all_goals)
    assert not any("it is unusable" in g.lower() or "no way to" in g.lower() for g in all_goals)
    # frustrations still carry the raw pains (they ARE the frustrations)
    all_frust = [f for p in personas for f in p.frustrations]
    assert any("unusable" in f.lower() for f in all_frust)


def test_prioritize_maps_severity_to_moscow():
    out = prioritize_features.TOOL.run(pain_points=PAINS, competitors=[])
    pri = {f.priority for f in out.payload}
    assert "Must" in pri  # high severity -> Must
    assert out.payload[0].priority == "Must"  # sorted Must-first


def test_user_stories_and_scope_and_ac():
    personas = generate_personas.TOOL.run(idea="x", pain_points=PAINS).payload
    stories = generate_user_stories.TOOL.run(personas=personas, pain_points=PAINS).payload
    assert stories and stories[0].lower().startswith("as a")
    feats = prioritize_features.TOOL.run(pain_points=PAINS, competitors=[]).payload
    scope = define_mvp_scope.TOOL.run(features=feats).payload
    assert "MVP includes" in scope
    ac = acceptance_criteria.TOOL.run(features=feats).payload
    assert ac["requirements"] and ac["rows"][0]["criteria"]


def test_assemble_prd_validates():
    feats = [Feature(title="Parse PDFs", description="d", priority="Must")]
    out = assemble_prd.TOOL.run(idea="resume", features=feats, requirements=["r"])
    assert out.ok and isinstance(out.payload, PRD) and out.payload.idea == "resume"


# ---- architecture -----------------------------------------------------------
def _data_model():
    feats = [Feature(title="Resume parsing engine", description="d", priority="Must"),
             Feature(title="Candidate ranking", description="d", priority="Should")]
    return design_data_model.TOOL.run(features=feats, personas=[]).payload


def test_data_model_has_user_and_feature_entities():
    dm = _data_model()
    ents = dm["entities"]
    assert "User" in ents
    assert len(ents) >= 2
    assert "id" in ents["User"]["fields"]


def test_design_api_contract_emits_valid_openapi():
    dm = _data_model()
    doc = design_api_contract.TOOL.run(data_model=dm, idea="resume screening").payload
    # OpenAPI 3.0 structural validity
    assert doc["openapi"].startswith("3.")
    assert "title" in doc["info"] and "version" in doc["info"]
    assert doc["paths"], "must declare paths"
    assert doc["components"]["schemas"], "must declare component schemas"
    for path, ops in doc["paths"].items():
        assert path.startswith("/")
        verbs = [v for v in ("get", "post", "put", "delete") if v in ops]
        assert verbs, f"{path}: at least one operation"
        for v in verbs:
            assert "responses" in ops[v]


def test_stack_scale_arch_and_trd():
    scale = estimate_scale.TOOL.run(idea="resume saas", features=[], personas=[]).payload
    assert "scale" in scale.lower()
    stack = choose_tech_stack.TOOL.run(requirements=["AI scoring", "search match"],
                                       scale_estimate=scale).payload
    assert any("FastAPI" in s for s in stack)
    assert any("ML" in s or "search" in s.lower() for s in stack)
    arch = design_architecture.TOOL.run(stack=stack, data_model=_data_model()).payload
    assert arch["components"] and arch["data_flow"]
    trd = assemble_trd.TOOL.run(data_model=_data_model(),
                                api_spec=design_api_contract.TOOL.run(data_model=_data_model()).payload,
                                stack=stack, scale_estimate=scale).payload
    assert isinstance(trd, TRD) and trd.stack


# ---- execution --------------------------------------------------------------
def test_execution_pipeline_tools():
    feats = [Feature(title="Parse PDFs", description="d", priority="Must")]
    repo = plan_repo_structure.TOOL.run(idea="x", stack=["FastAPI", "Redis + worker", "ML"]).payload
    assert "backend/app/workers" in repo["dirs"] and "backend/app/ml" in repo["dirs"]
    backlog = generate_backlog.TOOL.run(features=feats, api_spec={"paths": {"/a": {}, "/b": {}}}).payload
    assert len(backlog) >= 3 and backlog[0]["id"].startswith("APS-")
    est = estimate_effort.TOOL.run(backlog=backlog).payload
    assert est["total_points"] > 0 and all("points" in b for b in est["backlog"])
    sprints = plan_sprints.TOOL.run(backlog=est["backlog"], velocity=8).payload
    assert sprints and all(s["points"] <= 8 or len(s["items"]) == 1 for s in sprints)
    roadmap = generate_roadmap.TOOL.run(sprints=sprints).payload
    assert "MVP" in roadmap
    cost = estimate_infra_cost.TOOL.run(stack=["FastAPI", "ML inference", "Redis"],
                                        scale_estimate="10k users").payload
    assert "$" in cost and "/mo" in cost


# ---- presentation -----------------------------------------------------------
def test_presentation_tools_produce_text():
    outline = generate_pitch_outline.TOOL.run(idea="resume", market_size="$3B",
                                              pain_points=PAINS, mvp_scope="MVP x").payload
    assert "Problem" in outline and "Ask" in outline
    demo = generate_demo_script.TOOL.run(idea="resume",
                                         features=[Feature(title="Parse", description="d")],
                                         personas=[Persona(name="R", role="recruiter")]).payload
    assert "Demo" in demo
    memo = generate_investor_memo.TOOL.run(idea="resume", market_size="$3B",
                                           competitors=[Competitor(name="Acme")]).payload
    assert "INVESTOR MEMO" in memo and "Acme" in memo
    brief = generate_judge_brief.TOOL.run(idea="resume", tool_count=52,
                                          artifacts=["PRD", "TRD"]).payload
    assert "Req1" in brief and "52" in brief
