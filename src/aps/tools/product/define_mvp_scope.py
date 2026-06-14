"""define_mvp_scope — cut the feature list down to a shippable MVP statement.

Deterministic: keep the 'Must' features, name them as the MVP, and explicitly defer the
rest. Returns a scope *string* (the shape PRD.mvp_scope expects). No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Feature


class Args(BaseModel):
    features: list[Feature] = Field(default_factory=list)


class DefineMvpScope(BaseTool):
    name = "define_mvp_scope"
    namespace = "product"
    description = (
        "Define MVP scope from a prioritized feature list: include the 'Must' features, "
        "explicitly defer the rest, and state the smallest slice that resolves the top "
        "pain. Use after prioritize_features to draw the v1 boundary."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        must = [f for f in args.features if f.priority == "Must"]
        later = [f for f in args.features if f.priority != "Must"]
        if not must and args.features:
            must = args.features[:3]
            later = args.features[3:]
        inc = "; ".join(f.title for f in must) or "core workflow only"
        deferred = "; ".join(f.title for f in later[:6]) or "none"
        scope = (
            f"MVP includes: {inc}. "
            f"Deferred to fast-follow: {deferred}. "
            f"Goal: smallest releasable slice that resolves the highest-severity pain."
        )
        return ToolResult(ok=True, payload=scope)


TOOL = DefineMvpScope()

if __name__ == "__main__":
    import json
    out = TOOL.run(features=[Feature(title="Parse PDFs reliably", description="x", priority="Must").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
