"""generate_investor_memo — a one-page investor memo from the full package.

Deterministic templating over market, competitors, scope and cost. Returns the memo
*string* (the shape PitchPackage.investor_memo expects). No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Competitor


class Args(BaseModel):
    idea: str = ""
    market_size: str = ""
    competitors: list[Competitor] = Field(default_factory=list)
    mvp_scope: str = ""
    infra_cost: str = ""


class GenerateInvestorMemo(BaseTool):
    name = "generate_investor_memo"
    namespace = "presentation"
    description = (
        "Generate a one-page investor memo (thesis, market, competition, plan, economics) "
        "from the full package. Use as the written companion to the pitch — grounded in "
        "the research, PRD, TRD and execution plan."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        comps = ", ".join(c.name for c in args.competitors[:5]) or "a fragmented field"
        memo = (
            f"INVESTOR MEMO — {args.idea}\n\n"
            f"Thesis: solve an evidenced user pain with a focused MVP.\n"
            f"Market: {args.market_size or 'sized from demand signals in the research.'}\n"
            f"Competition: {comps}. Wedge = the unmet pain incumbents ignore.\n"
            f"Plan: {args.mvp_scope or 'ship the MVP, validate with design partners.'}\n"
            f"Economics: {args.infra_cost or 'lean infra at MVP; scales with usage.'}\n"
            f"Ask: capital/pilot to reach validated traction."
        )
        return ToolResult(ok=True, payload=memo)


TOOL = GenerateInvestorMemo()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening", market_size="$3B TAM",
                   competitors=[Competitor(name="ExampleATS").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
