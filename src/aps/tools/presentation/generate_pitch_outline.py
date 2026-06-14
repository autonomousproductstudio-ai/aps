"""generate_pitch_outline — a problem→solution→ask pitch outline from the artifacts.

Deterministic templating over the real upstream data (idea, market size, top pains, MVP
scope). Returns the outline *string*. The agent composes; the tool structures. No LLM.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, PainPoint


class Args(BaseModel):
    idea: str = ""
    market_size: str = ""
    pain_points: list[PainPoint] = Field(default_factory=list)
    mvp_scope: str = ""


class GeneratePitchOutline(BaseTool):
    name = "generate_pitch_outline"
    namespace = "presentation"
    description = (
        "Generate a pitch outline (problem → solution → market → ask) grounded in the "
        "research and PRD. Use to produce the slide skeleton the investor memo and demo "
        "build on."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        pains = "; ".join(p.text for p in args.pain_points[:3]) or "a real, evidenced user pain"
        outline = (
            f"1. Problem — {pains}.\n"
            f"2. Solution — {args.idea}: {args.mvp_scope or 'an MVP that resolves the top pain'}.\n"
            f"3. Market — {args.market_size or 'sized from demand signals in the research'}.\n"
            f"4. Why now / why us — evidence-grounded wedge into the top pain.\n"
            f"5. Ask — funding/pilot to ship the MVP and validate with design partners."
        )
        return ToolResult(ok=True, payload=outline)


TOOL = GeneratePitchOutline()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening", market_size="$3B TAM",
                   pain_points=[PainPoint(text="parser drops PDFs").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
