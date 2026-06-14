"""Presentation Agent (P2, thin). Consumes the whole StudioState, emits a PitchPackage.

Deterministic pipeline over the scoped presentation tools (ADR-0005): pitch outline →
demo script → investor memo → judge brief. The frozen `PitchPackage` has three fields
(pitch_outline, demo_script, investor_memo), so the judge brief is folded into the memo
rather than expanding the contract — see decision.md D4.
"""
from __future__ import annotations

from aps.state.models import StudioState, PitchPackage
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS


def run_presentation(state: StudioState) -> PitchPackage:
    AGENT_RUNS.labels(agent="presentation").inc()
    t = scoped("presentation")

    research = state.research
    prd = state.prd
    execution = state.execution

    market_size = research.market_size if research else ""
    pain_points = research.pain_points if research else []
    competitors = research.competitors if research else []
    features = prd.features if prd else []
    personas = prd.personas if prd else []
    mvp_scope = prd.mvp_scope if prd else ""
    infra_cost = execution.infra_cost if execution else ""

    artifacts = [name for name, present in (
        ("Research", research is not None), ("PRD", prd is not None),
        ("TRD", state.trd is not None), ("ExecutionPlan", execution is not None),
    ) if present]

    pitch_outline = call(t, "generate_pitch_outline",
                         idea=state.idea, market_size=market_size,
                         pain_points=pain_points, mvp_scope=mvp_scope)
    demo_script = call(t, "generate_demo_script",
                       idea=state.idea, features=features, personas=personas)
    memo = call(t, "generate_investor_memo",
                idea=state.idea, market_size=market_size, competitors=competitors,
                mvp_scope=mvp_scope, infra_cost=infra_cost)
    from aps.tools.registry import all_tools
    brief = call(t, "generate_judge_brief",
                 idea=state.idea, tool_count=len(all_tools()), artifacts=artifacts)

    return PitchPackage(
        pitch_outline=pitch_outline,
        demo_script=demo_script,
        investor_memo=memo + "\n\n---\n" + brief,
    )
