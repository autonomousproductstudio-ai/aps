"""plan_repo_structure — propose a repo layout from the chosen stack.

Deterministic: a sensible monorepo skeleton (backend/frontend/infra/tests/docs),
extended with stack-specific dirs (ml/, workers/) when the stack mentions them.
Returns {dirs: [...], key_files: [...]}. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult


class Args(BaseModel):
    idea: str = ""
    stack: list[str] = Field(default_factory=list)


class PlanRepoStructure(BaseTool):
    name = "plan_repo_structure"
    namespace = "execution"
    description = (
        "Plan the repository structure from the stack: directories and key files for a "
        "buildable monorepo, with stack-specific folders (workers, ml) added when "
        "relevant. Use first in execution planning to anchor the backlog in real paths."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        blob = " ".join(args.stack).lower()
        dirs = ["backend/app", "backend/app/api", "backend/app/models",
                "backend/tests", "frontend/src", "infra", "docs"]
        if "worker" in blob or "queue" in blob or "redis" in blob:
            dirs.append("backend/app/workers")
        if "ml" in blob or "inference" in blob or "llm" in blob:
            dirs.append("backend/app/ml")
        key_files = ["backend/app/main.py", "backend/app/api/routes.py",
                     "backend/app/models/schema.py", "backend/Dockerfile",
                     "frontend/package.json", "infra/docker-compose.yml",
                     "README.md", ".github/workflows/ci.yml"]
        return ToolResult(ok=True, payload={"dirs": dirs, "key_files": key_files})


TOOL = PlanRepoStructure()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening", stack=["FastAPI", "Redis + worker queue", "ML serving"])
    print(json.dumps(out.model_dump(), indent=2, default=str))
