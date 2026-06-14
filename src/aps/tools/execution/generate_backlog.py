"""generate_backlog — turn features + API endpoints into backlog items.

Deterministic: one story per feature (carrying its priority) plus one task per OpenAPI
path group, plus baseline platform tasks (auth, CI, deploy). Returns a list of backlog
dicts {id, title, type, priority}. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Feature


class Args(BaseModel):
    features: list[Feature] = Field(default_factory=list)
    api_spec: dict = Field(default_factory=dict)
    requirements: list[str] = Field(default_factory=list)


class GenerateBacklog(BaseTool):
    name = "generate_backlog"
    namespace = "execution"
    description = (
        "Generate a development backlog from features and the API spec: a story per "
        "feature (with priority), a task per endpoint group, and baseline platform tasks "
        "(auth, CI, deploy). Use to convert the PRD/TRD into trackable work items."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        items: list[dict] = []
        n = 0

        def add(title: str, type_: str, priority: str = "Should") -> None:
            nonlocal n
            n += 1
            items.append({"id": f"APS-{n:03d}", "title": title, "type": type_,
                          "priority": priority})

        for f in args.features:
            add(f"Implement: {f.title}", "story", f.priority)
        for path in (args.api_spec.get("paths", {}) or {}):
            add(f"Build API endpoint {path}", "task")
        if not args.features and args.requirements:
            for r in args.requirements:
                add(f"Requirement: {r[:70]}", "story")
        for base in ("Set up auth & user accounts", "CI pipeline (lint + tests)",
                     "Containerize & deploy MVP", "Observability (logs + metrics)"):
            add(base, "task", "Must" if "auth" in base.lower() else "Should")
        return ToolResult(ok=True, payload=items)


TOOL = GenerateBacklog()

if __name__ == "__main__":
    import json
    out = TOOL.run(features=[Feature(title="Parse PDFs", description="x", priority="Must").model_dump()],
                   api_spec={"paths": {"/resumes": {}, "/users": {}}})
    print(json.dumps(out.model_dump(), indent=2, default=str))
