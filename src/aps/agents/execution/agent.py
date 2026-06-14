"""Execution Agent (P2, thin). Consumes TRD (+ optional PRD), emits an ExecutionPlan.

Deterministic pipeline over the scoped execution tools (ADR-0005): repo structure →
backlog → effort → sprints → roadmap → infra cost. The TRD carries the stack, API spec
and scale used to size everything; the PRD (when available) enriches the backlog with
the actual feature stories. `estimate_infra_cost` reuses the real stack/scale signals.
"""
from __future__ import annotations

from aps.state.models import TRD, PRD, ExecutionPlan
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS


def run_execution(trd: TRD, prd: PRD | None = None) -> ExecutionPlan:
    AGENT_RUNS.labels(agent="execution").inc()
    t = scoped("execution")

    idea = prd.idea if prd else ""
    features = prd.features if prd else []
    requirements = prd.requirements if prd else []

    repo_plan = call(t, "plan_repo_structure", idea=idea, stack=trd.stack)
    backlog = call(t, "generate_backlog",
                   features=features, api_spec=trd.api_spec, requirements=requirements)
    estimated = call(t, "estimate_effort", backlog=backlog)
    backlog = estimated["backlog"]
    sprints = call(t, "plan_sprints", backlog=backlog, velocity=13)
    roadmap = call(t, "generate_roadmap", sprints=sprints)
    infra_cost = call(t, "estimate_infra_cost",
                      stack=trd.stack, scale_estimate=trd.scale_estimate)

    return ExecutionPlan(
        repo_plan=repo_plan,
        backlog=backlog,
        sprints=sprints,
        roadmap=roadmap,
        infra_cost=infra_cost,
    )
