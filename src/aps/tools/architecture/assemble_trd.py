"""assemble_trd — VALIDATE the parts into a schema-valid TRD (ADR-0004).

Like assemble_prd: not a generator. Takes the data model, OpenAPI spec, stack and scale
estimate the agent produced and validates them into the frozen `TRD` type, or returns a
typed error.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, TRD


class Args(BaseModel):
    data_model: dict = Field(default_factory=dict)
    api_spec: dict = Field(default_factory=dict)
    stack: list[str] = Field(default_factory=list)
    scale_estimate: str = ""


class AssembleTRD(BaseTool):
    name = "assemble_trd"
    namespace = "architecture"
    description = (
        "Assemble and VALIDATE the final TRD from its parts (data model, OpenAPI spec, "
        "stack, scale estimate). Schema gate, not a generator — guarantees the TRD "
        "conforms to the contract or returns an error."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            trd = TRD(
                data_model=args.data_model,
                api_spec=args.api_spec,
                stack=args.stack,
                scale_estimate=args.scale_estimate,
            )
        except ValidationError as e:
            return ToolResult(ok=False, error=f"TRD validation failed: {e}")
        return ToolResult(ok=True, payload=trd)


TOOL = AssembleTRD()

if __name__ == "__main__":
    import json
    out = TOOL.run(stack=["FastAPI", "PostgreSQL"], scale_estimate="10k users")
    print(json.dumps(out.model_dump(), indent=2, default=str))
