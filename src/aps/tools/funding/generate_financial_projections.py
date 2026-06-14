"""generate_financial_projections — an illustrative 3-year model.

Deterministic: parses a TAM reference from the research market-size statement and the infra
spend from the execution estimate, then builds a 3-year revenue/cost/net model on clearly
labelled assumptions (surfaced in `notes`). NOT a forecast. Returns the model dict.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.funding import _finance


class Args(BaseModel):
    market_size: str = ""
    infra_cost: str = ""
    assumptions: dict[str, Any] = Field(default_factory=dict)


class GenerateFinancialProjections(BaseTool):
    name = "generate_financial_projections"
    namespace = "funding"
    description = (
        "Build an illustrative 3-year financial model (customers, revenue, gross profit, opex, "
        "net) from the research TAM and the execution infra estimate, on explicit, surfaced "
        "assumptions. Deterministic; an illustration, not a forecast."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        model = _finance.project(args.market_size, args.infra_cost, args.assumptions)
        return ToolResult(ok=True, payload=model)


TOOL = GenerateFinancialProjections()

if __name__ == "__main__":
    import json
    print(json.dumps(TOOL.run(market_size="~$3B market", infra_cost="$400/mo").payload, indent=2))
