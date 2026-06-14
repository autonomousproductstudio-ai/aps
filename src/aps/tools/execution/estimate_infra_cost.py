"""estimate_infra_cost — rough monthly infra cost from the stack + scale.

Deterministic: a small line-item pricing table (compute, db, cache, ml, search) summed
according to which components the stack uses and the scale tier. Returns a cost *string*
with the line items. Not a quote — an order-of-magnitude planning number. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult

# rough USD/month at MVP scale (single small instance each)
_PRICE = {"compute": 40, "db": 25, "cache": 15, "worker": 25, "ml": 120,
          "search": 50, "egress": 10}


class Args(BaseModel):
    stack: list[str] = Field(default_factory=list)
    scale_estimate: str = ""


class EstimateInfraCost(BaseTool):
    name = "estimate_infra_cost"
    namespace = "execution"
    description = (
        "Estimate rough monthly infrastructure cost from the stack and scale, as summed "
        "line items (compute, db, cache, ml, search). Use to give the plan a realistic "
        "burn figure — an order-of-magnitude planning number, not a vendor quote."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        blob = " ".join(args.stack).lower()
        scale = args.scale_estimate.lower()
        mult = 3 if any(k in scale for k in ("1m", "million", "high", "2000")) else 1
        items: dict[str, int] = {"compute": _PRICE["compute"], "db": _PRICE["db"],
                                 "egress": _PRICE["egress"]}
        if "redis" in blob or "cache" in blob:
            items["cache"] = _PRICE["cache"]
        if "worker" in blob or "queue" in blob:
            items["worker"] = _PRICE["worker"]
        if "ml" in blob or "inference" in blob or "llm" in blob:
            items["ml"] = _PRICE["ml"]
        if "search" in blob or "pgvector" in blob or "opensearch" in blob:
            items["search"] = _PRICE["search"]
        total = sum(v * mult for v in items.values())
        breakdown = ", ".join(f"{k} ${v * mult}" for k, v in items.items())
        stmt = (f"Estimated infra ~${total}/mo at this scale ({breakdown}). "
                f"Scales roughly linearly; assumes managed services, no committed-use discounts.")
        return ToolResult(ok=True, payload=stmt)


TOOL = EstimateInfraCost()

if __name__ == "__main__":
    import json
    out = TOOL.run(stack=["FastAPI", "PostgreSQL", "Redis + worker", "ML inference"],
                   scale_estimate="10k users")
    print(json.dumps(out.model_dump(), indent=2, default=str))
