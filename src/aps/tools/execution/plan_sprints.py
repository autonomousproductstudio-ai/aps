"""plan_sprints — pack the estimated backlog into fixed-velocity sprints.

Deterministic bin-packing by velocity (points/sprint), preserving order (priority-first
if the backlog is already sorted). Returns a list of sprint dicts {sprint, items[],
points}. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult


class Args(BaseModel):
    backlog: list[dict] = Field(default_factory=list)
    velocity: int = Field(13, ge=1, le=100, description="points per sprint")
    max_sprints: int = Field(8, ge=1, le=24)


class PlanSprints(BaseTool):
    name = "plan_sprints"
    namespace = "execution"
    description = (
        "Plan sprints by packing the estimated backlog into fixed-velocity buckets, in "
        "priority order. Use after estimate_effort to produce a realistic delivery "
        "sequence the roadmap is built from."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        sprints: list[dict] = []
        cur: list[dict] = []
        cur_pts = 0
        idx = 1
        for item in args.backlog:
            pts = int(item.get("points", 3))
            if cur and cur_pts + pts > args.velocity:
                sprints.append({"sprint": idx, "items": cur, "points": cur_pts})
                idx += 1
                cur, cur_pts = [], 0
                if idx > args.max_sprints:
                    break
            cur.append(item)
            cur_pts += pts
        if cur and idx <= args.max_sprints:
            sprints.append({"sprint": idx, "items": cur, "points": cur_pts})
        return ToolResult(ok=True, payload=sprints)


TOOL = PlanSprints()

if __name__ == "__main__":
    import json
    bl = [{"id": f"APS-{i}", "title": "x", "points": 5} for i in range(6)]
    out = TOOL.run(backlog=bl, velocity=13)
    print(json.dumps(out.model_dump(), indent=2, default=str))
