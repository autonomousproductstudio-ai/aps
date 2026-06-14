"""assemble_prd — VALIDATE the parts into a schema-valid PRD (ADR-0004).

This tool does NOT ask a model to write a PRD. It takes the structured parts the agent
already produced (personas, features, scope, requirements, sources) and validates them
into the frozen `PRD` type. If validation fails, it returns a typed error instead of a
half-baked artifact. The 'writing' was the agent's reasoning; this is the schema gate.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, PRD, Persona, Feature, Evidence


class Args(BaseModel):
    idea: str
    personas: list[Persona] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    mvp_scope: str = ""
    requirements: list[str] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)


class AssemblePRD(BaseTool):
    name = "assemble_prd"
    namespace = "product"
    description = (
        "Assemble and VALIDATE the final PRD from its already-produced parts (personas, "
        "features, MVP scope, requirements, sources). This is a schema gate, not a "
        "generator — it guarantees the PRD conforms to the contract or returns an error."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            prd = PRD(
                idea=args.idea,
                personas=args.personas,
                features=args.features,
                mvp_scope=args.mvp_scope,
                requirements=args.requirements,
                sources=args.sources,
            )
        except ValidationError as e:
            return ToolResult(ok=False, error=f"PRD validation failed: {e}")
        return ToolResult(ok=True, payload=prd)


TOOL = AssemblePRD()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening", requirements=["[Must] Parse PDFs"])
    print(json.dumps(out.model_dump(), indent=2, default=str))
