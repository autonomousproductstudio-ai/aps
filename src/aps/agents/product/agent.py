"""Product Agent (P2). Consumes ResearchReturn, emits a schema-valid PRD.

Deterministic pipeline over the agent's *scoped* product tools (ADR-0005): personas →
user stories → prioritized features → MVP scope → acceptance criteria → assemble.
`assemble_prd` VALIDATES the parts into the PRD; it does not re-generate (ADR-0004).
The reasoning ('which pains become features, what's in the MVP') lives in this pipeline;
the tools are the verbs. See decision.md D2 for why this is deterministic, not an LLM loop.
"""
from __future__ import annotations

from aps.state.models import ResearchReturn, PRD
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS


def run_product(research: ResearchReturn) -> PRD:
    AGENT_RUNS.labels(agent="product").inc()
    t = scoped("product")

    personas = call(t, "generate_personas",
                    idea=research.idea, pain_points=research.pain_points)
    stories = call(t, "generate_user_stories",
                   personas=personas, pain_points=research.pain_points)
    features = call(t, "prioritize_features",
                    pain_points=research.pain_points, competitors=research.competitors)
    mvp_scope = call(t, "define_mvp_scope", features=features)
    ac = call(t, "acceptance_criteria", features=features)

    requirements = list(ac.get("requirements", []))
    requirements += [f"User story: {s}" for s in stories]

    prd: PRD = call(t, "assemble_prd",
                    idea=research.idea, personas=personas, features=features,
                    mvp_scope=mvp_scope, requirements=requirements,
                    sources=research.evidence)
    return prd
