"""generate_fundraising_roadmap — round sequence + use-of-funds.

Deterministic: a standard pre-seed → seed → Series A ladder, with the current ask sized from
the model, use-of-funds allocation, and milestones drawn from the execution roadmap. Returns
{current_ask, use_of_funds, rounds}. No LLM, no network.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult


class Args(BaseModel):
    company_name: str = ""
    roadmap: str = ""                                   # execution roadmap (milestone text)
    runway_months: int = Field(18, ge=6, le=36)
    current_ask: str = ""                               # optional override


class GenerateFundraisingRoadmap(BaseTool):
    name = "generate_fundraising_roadmap"
    namespace = "funding"
    description = (
        "Generate a fundraising roadmap: the pre-seed → seed → Series A round ladder with "
        "indicative amounts, timing, use-of-funds allocation, and milestones tied to the "
        "execution roadmap. Deterministic; indicative ranges, not commitments."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        company = args.company_name or "[COMPANY]"
        # First non-empty roadmap line as the near-term milestone anchor.
        first_milestone = next(
            (ln.strip(" -•\t") for ln in (args.roadmap or "").splitlines() if ln.strip()),
            "Ship the MVP and onboard design partners",
        )
        ask = args.current_ask or "[PRE-SEED AMOUNT, e.g. $500K–$1M]"

        use_of_funds: list[dict[str, Any]] = [
            {"area": "Product & engineering", "pct": 45,
             "detail": "Ship the MVP and the next roadmap milestones"},
            {"area": "Go-to-market", "pct": 30,
             "detail": "Launch motion + design-partner pilots → self-serve"},
            {"area": "Key hires", "pct": 20, "detail": "First engineering + GTM hires"},
            {"area": "Operations & buffer", "pct": 5, "detail": "Infra, legal, contingency"},
        ]
        rounds: list[dict[str, Any]] = [
            {"round": "Pre-seed", "amount": ask, "timing": "Now",
             "milestones": f"{first_milestone}; reach first paying pilots"},
            {"round": "Seed", "amount": "[SEED AMOUNT, e.g. $2M–$4M]",
             "timing": f"~{args.runway_months} months / on traction",
             "milestones": "Repeatable acquisition; early ARR; expand the team"},
            {"round": "Series A", "amount": "[SERIES A AMOUNT, e.g. $8M–$15M]",
             "timing": "On clear product-market fit",
             "milestones": "Scale GTM; durable growth; new product lines"},
        ]
        return ToolResult(ok=True, payload={
            "company_name": company,
            "current_ask": ask,
            "use_of_funds": use_of_funds,
            "rounds": rounds,
        })


TOOL = GenerateFundraisingRoadmap()

if __name__ == "__main__":
    import json
    print(json.dumps(TOOL.run(company_name="Habitly",
                              roadmap="Sprint 1: auth\nSprint 2: tracking").payload, indent=2))
