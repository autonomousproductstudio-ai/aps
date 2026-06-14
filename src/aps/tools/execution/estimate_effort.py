"""estimate_effort — assign story points to backlog items.

Deterministic: points from item type and priority (stories cost more than tasks, Must
items get a complexity bump). Returns the backlog with `points` added and a total. No LLM.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult

_BASE = {"story": 5, "task": 3, "spike": 2, "bug": 2}
_PRI_BUMP = {"Must": 2, "Should": 1, "Could": 0, "Won't": 0}
_FIB = [1, 2, 3, 5, 8, 13]


def _nearest_fib(n: int) -> int:
    return min(_FIB, key=lambda f: abs(f - n))


class Args(BaseModel):
    backlog: list[dict] = Field(default_factory=list)


class EstimateEffort(BaseTool):
    name = "estimate_effort"
    namespace = "execution"
    description = (
        "Estimate effort (Fibonacci story points) for each backlog item from its type and "
        "priority, returning the annotated backlog and a total. Use after generate_backlog "
        "so sprints can be planned against real capacity."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        out = []
        total = 0
        for item in args.backlog:
            raw = _BASE.get(item.get("type", "task"), 3) + _PRI_BUMP.get(item.get("priority", "Should"), 1)
            pts = _nearest_fib(raw)
            total += pts
            out.append({**item, "points": pts})
        return ToolResult(ok=True, payload={"backlog": out, "total_points": total})


TOOL = EstimateEffort()

if __name__ == "__main__":
    import json
    out = TOOL.run(backlog=[{"id": "APS-001", "title": "x", "type": "story", "priority": "Must"}])
    print(json.dumps(out.model_dump(), indent=2, default=str))
