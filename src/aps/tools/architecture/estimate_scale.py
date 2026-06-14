"""estimate_scale — a rough scale/SLO statement from PRD signals.

Deterministic heuristic over feature/persona counts and keyword cues (b2b vs consumer,
realtime, batch). Returns a scale_estimate *string* for the TRD. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Feature, Persona


class Args(BaseModel):
    idea: str = ""
    features: list[Feature] = Field(default_factory=list)
    personas: list[Persona] = Field(default_factory=list)


class EstimateScale(BaseTool):
    name = "estimate_scale"
    namespace = "architecture"
    description = (
        "Estimate scale and rough SLOs (user tier, RPS ballpark, latency target) from the "
        "PRD's size and keywords. Use to right-size the stack and infra cost — an "
        "order-of-magnitude read, not a capacity plan."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        blob = (args.idea + " " + " ".join(f.title for f in args.features)).lower()
        consumer = any(k in blob for k in ("consumer", "social", "viral", "everyone", "personal"))
        realtime = any(k in blob for k in ("realtime", "live", "chat", "stream"))
        tier = "10k–100k users (early B2B SaaS)" if not consumer else "100k–1M users (consumer)"
        rps = "~50–200 RPS peak" if not consumer else "~500–2000 RPS peak"
        latency = "p95 < 300ms reads" + ("; sub-second realtime updates" if realtime else "")
        stmt = (f"Target scale: {tier}; {rps}; {latency}. "
                f"{len(args.features)} features, {len(args.personas)} persona(s) drive a "
                f"single-region deployment at MVP, horizontally scalable behind a load balancer.")
        return ToolResult(ok=True, payload=stmt)


TOOL = EstimateScale()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening SaaS",
                   features=[Feature(title="parse", description="x").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
