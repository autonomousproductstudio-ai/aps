"""Funding Agent (Launch Studio Phase 3, thin/deterministic).

Consumes the StudioState, emits a FundingPackage: an investor pitch-deck outline, an
illustrative 3-year financial model, and a fundraising roadmap. A deterministic pipeline over
the scoped `funding` tools (ADR-0005) — same shape as the Brand/Legal agents — so it adds
~1–2s, runs in a parallel graph branch, and needs no LLM key.

It reuses data already produced upstream: market size/pains/competitors from Research, the
feature set + MVP scope from the PRD, and infra cost + roadmap from the Execution plan. Runs
after `execution`, so all three are present. The financials are an illustration on explicit
assumptions, never a forecast.
"""
from __future__ import annotations

from aps.state.models import StudioState, FundingPackage
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS
from aps.tools.brand._svg import derive_name


def run_funding(state: StudioState) -> FundingPackage:
    AGENT_RUNS.labels(agent="funding").inc()
    t = scoped("funding")

    idea = state.idea
    research = state.research
    prd = state.prd
    execution = state.execution

    company_name = (state.brand.name if state.brand and state.brand.name
                    else derive_name(idea))
    market_size = research.market_size if research else ""
    pain_points = research.pain_points if research else []
    competitors = research.competitors if research else []
    features = prd.features if prd else []
    mvp_scope = prd.mvp_scope if prd else ""
    infra_cost = execution.infra_cost if execution else ""
    roadmap = execution.roadmap if execution else ""

    financials = call(t, "generate_financial_projections",
                      market_size=market_size, infra_cost=infra_cost)
    roadmap_pack = call(t, "generate_fundraising_roadmap",
                        company_name=company_name, roadmap=roadmap)
    ask = roadmap_pack["current_ask"]
    deck = call(t, "generate_pitch_deck_outline",
                company_name=company_name, idea=idea, market_size=market_size,
                pain_points=pain_points, competitors=competitors,
                features=features, mvp_scope=mvp_scope, ask=ask)

    return FundingPackage(
        company_name=company_name,
        ask=ask,
        deck_slides=deck,
        financials=financials,
        use_of_funds=roadmap_pack["use_of_funds"],
        rounds=roadmap_pack["rounds"],
    )
