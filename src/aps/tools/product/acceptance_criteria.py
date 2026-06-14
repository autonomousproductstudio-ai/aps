"""acceptance_criteria — attach Given/When/Then criteria to each feature.

Deterministic templating: every feature gets testable acceptance criteria so the PRD's
requirements are verifiable. Returns a list of {feature, criteria[]} plus a flat list of
requirement strings the PRD can adopt. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Feature


class Args(BaseModel):
    features: list[Feature] = Field(default_factory=list)


class AcceptanceCriteria(BaseTool):
    name = "acceptance_criteria"
    namespace = "product"
    description = (
        "Generate testable Given/When/Then acceptance criteria for each feature, so the "
        "PRD's requirements are verifiable rather than vague. Use after MVP scope is set "
        "to turn features into checkable requirements."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        rows = []
        requirements: list[str] = []
        for f in args.features:
            crit = [
                f"Given a user with this need, when they use '{f.title}', then the "
                f"primary pain is resolved without manual workaround.",
                f"Given invalid or edge input, when '{f.title}' runs, then it fails "
                f"gracefully with a clear message.",
            ]
            rows.append({"feature": f.title, "priority": f.priority, "criteria": crit})
            requirements.append(f"[{f.priority}] {f.title}: {f.description}")
        return ToolResult(ok=True, payload={"rows": rows, "requirements": requirements})


TOOL = AcceptanceCriteria()

if __name__ == "__main__":
    import json
    out = TOOL.run(features=[Feature(title="Parse PDFs", description="reliable parsing", priority="Must").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
