"""generate_personas — derive user personas from research (pains + competitors).

Deterministic verb: turns the top pain points into 1–3 personas, mapping pains to
frustrations and their inverse to goals. The Product agent reasons over the result; the
tool just does the structured transform (ADR-0004). No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, PainPoint, Persona
from aps.tools.analysis._text import pain_to_feature_title

_ROLES = ["Primary user", "Team lead / buyer", "Power user"]


class Args(BaseModel):
    idea: str = ""
    pain_points: list[PainPoint] = Field(default_factory=list)
    max_personas: int = Field(3, ge=1, le=5)


class GeneratePersonas(BaseTool):
    name = "generate_personas"
    namespace = "product"
    description = (
        "Generate user personas from research pain points: each persona gets a role, "
        "goals (the inverse of the pains) and frustrations (the pains themselves). Use "
        "first in PRD assembly to ground personas in real evidence, not imagination."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        pains = args.pain_points
        frustrations = [p.text for p in pains]
        n = min(args.max_personas, max(1, (len(pains) + 1) // 2)) if pains else 1
        personas: list[Persona] = []
        for i in range(n):
            chunk = frustrations[i::n] or ["unmet need in this space"]
            # GOALS are the positive inverse of the pains → the capability the user wants,
            # not a "Resolve: <raw complaint>" paste ("Resolve: It is unusable"). FRUSTRATIONS
            # stay the raw pains (they ARE the frustrations). Dedupe goals within the persona.
            goals: list[str] = []
            for c in chunk[:3]:
                cap = pain_to_feature_title(c) if c.strip() else c
                if cap and cap not in goals:
                    goals.append(cap)
            personas.append(Persona(
                name=f"{_ROLES[i % len(_ROLES)]}",
                role=_ROLES[i % len(_ROLES)],
                goals=goals or ["Accomplish the core task"],
                frustrations=chunk[:4],
            ))
        return ToolResult(ok=True, payload=personas)


TOOL = GeneratePersonas()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening",
                   pain_points=[PainPoint(text="parser drops PDFs").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
