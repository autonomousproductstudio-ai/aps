"""generate_roadmap — a milestone narrative from the sprint plan.

Deterministic: groups sprints into phases (MVP / Beta / GA) and writes a short roadmap
string with what lands when. Returns the roadmap *string* for ExecutionPlan.roadmap. No LLM.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult

_PHASES = ["MVP", "Beta", "GA", "Scale"]


class Args(BaseModel):
    sprints: list[dict] = Field(default_factory=list)


class GenerateRoadmap(BaseTool):
    name = "generate_roadmap"
    namespace = "execution"
    description = (
        "Generate a milestone roadmap (MVP → Beta → GA) from the sprint plan, naming what "
        "ships in each phase. Use after plan_sprints to give stakeholders the timeline view."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        sprints = args.sprints
        if not sprints:
            return ToolResult(ok=True, payload="No sprints planned yet.")
        per = max(1, (len(sprints) + len(_PHASES) - 1) // len(_PHASES))
        lines = []
        for i in range(0, len(sprints), per):
            phase = _PHASES[min(i // per, len(_PHASES) - 1)]
            group = sprints[i:i + per]
            titles = [it.get("title", "") for s in group for it in s.get("items", [])]
            head = "; ".join(t for t in titles[:4] if t) or "core work"
            lines.append(f"{phase} (sprints {group[0].get('sprint')}–{group[-1].get('sprint')}): {head}.")
        return ToolResult(ok=True, payload=" \n".join(lines))


TOOL = GenerateRoadmap()

if __name__ == "__main__":
    import json
    sp = [{"sprint": 1, "items": [{"title": "auth"}]}, {"sprint": 2, "items": [{"title": "core"}]}]
    out = TOOL.run(sprints=sp)
    print(json.dumps(out.model_dump(), indent=2, default=str))
