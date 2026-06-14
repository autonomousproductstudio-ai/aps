"""generate_pitch_deck_outline — a full investor pitch-deck outline (slide by slide).

Deterministic: assembles the standard 11-slide deck from the Research/PRD facts already in
state. Returns a list of slides ({title, bullets}). No LLM, no network.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, PainPoint, Competitor, Feature


class Args(BaseModel):
    company_name: str = ""
    idea: str = ""
    market_size: str = ""
    pain_points: list[PainPoint] = Field(default_factory=list)
    competitors: list[Competitor] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    mvp_scope: str = ""
    ask: str = ""


class GeneratePitchDeckOutline(BaseTool):
    name = "generate_pitch_deck_outline"
    namespace = "funding"
    description = (
        "Generate a slide-by-slide investor pitch deck outline (title, problem, solution, "
        "product, market, competition, business model, traction, team, ask) grounded in the "
        "research and PRD. Deterministic; returns a list of slides."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        company = args.company_name or "[COMPANY]"
        pains = [p.text for p in args.pain_points[:3]] or ["A real, evidenced user pain"]
        feats = [f.title for f in args.features[:4]] or ["The MVP capability set"]
        comps = [c.name for c in args.competitors[:4]] or ["Incumbents and manual workarounds"]

        slides: list[dict[str, Any]] = [
            {"title": f"{company}", "bullets": [
                args.idea or "[one-line product description]",
                "Investor deck — [DATE]"]},
            {"title": "Problem", "bullets": pains},
            {"title": "Solution", "bullets": [
                f"{company}: {args.mvp_scope or 'an MVP that resolves the top pain'}",
                "Evidence-grounded, automated end to end"]},
            {"title": "Product", "bullets": feats},
            {"title": "Market", "bullets": [
                args.market_size or "[TAM/SAM/SOM sized from research demand signals]",
                "Bottoms-up demand evidenced in the research"]},
            {"title": "Competition", "bullets": [
                "Landscape: " + ", ".join(comps),
                "Our wedge: the top evidenced pain incumbents ignore"]},
            {"title": "Business Model", "bullets": [
                "SaaS subscription — [PRICING]",
                "Land on the MVP wedge, expand across the feature set"]},
            {"title": "Go-to-Market", "bullets": [
                "Launch motion from the brand campaign (Product Hunt / Show HN / communities)",
                "Design-partner pilots → self-serve"]},
            {"title": "Traction & Roadmap", "bullets": [
                "[CURRENT TRACTION — pilots, waitlist, revenue]",
                "Roadmap milestones from the execution plan"]},
            {"title": "Team", "bullets": [
                "[FOUNDER NAMES + relevant background]",
                "[KEY HIRES the raise funds]"]},
            {"title": "The Ask", "bullets": [
                args.ask or "Raising [AMOUNT] to ship the MVP and validate with design partners",
                "Use of funds: product, GTM, key hires (see funding roadmap)"]},
        ]
        return ToolResult(ok=True, payload=slides)


TOOL = GeneratePitchDeckOutline()

if __name__ == "__main__":
    import json
    out = TOOL.run(company_name="Habitly", idea="a privacy-first habit tracker",
                   market_size="~$1.2B market")
    print(json.dumps(out.payload, indent=2))
