"""generate_brand_identity — name → taglines + positioning, derived from the idea.

Deterministic templating over a CLEANED idea phrase (reuses the analysis-side `clean_label`
via `_svg.clean_core`) so copy never bleeds raw snippet/markdown text. Returns a dict
{name, positioning, taglines}.
"""
from __future__ import annotations

from pydantic import BaseModel

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.brand import _svg


class Args(BaseModel):
    idea: str
    name: str = ""   # optional; derived from the idea when empty


class GenerateBrandIdentity(BaseTool):
    name = "generate_brand_identity"
    namespace = "brand"
    description = (
        "Produce a brand identity from a product idea: a name (derived when not given), a "
        "set of taglines, and a positioning statement. Deterministic; copy is normalized so "
        "the raw idea text never bleeds into the taglines."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        name = args.name.strip() or _svg.derive_name(args.idea)
        core = _svg.clean_core(args.idea)
        low = core[0].lower() + core[1:] if core else core
        taglines = [
            f"{name} — {core}, done for you.",
            f"Ship faster with {name}.",
            f"The smart way to {low}.",
            f"{name}: less busywork, more building.",
            f"Your {low}, on autopilot.",
        ]
        positioning = (
            f"For teams who need {low} without the overhead, {name} is the tool that "
            f"automates the busywork end to end — so you focus on the work that actually "
            f"moves the needle."
        )
        return ToolResult(ok=True, payload={
            "name": name, "positioning": positioning, "taglines": taglines,
        })


TOOL = GenerateBrandIdentity()

if __name__ == "__main__":
    import json
    print(json.dumps(TOOL.run(idea="AI-powered accounting for SMEs").payload, indent=2))
