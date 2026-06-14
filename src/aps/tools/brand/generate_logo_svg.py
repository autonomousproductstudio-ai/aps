"""generate_logo_svg — a deterministic inline-SVG logo (mark + optional wordmark).

No image model, no network: the name seeds a palette and a mark style (stack/orbit/hex),
the mark renders as inline SVG. Returns the SVG *string*. The agent composes; the tool
structures (decision D2).
"""
from __future__ import annotations

from pydantic import BaseModel

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.brand import _svg


class Args(BaseModel):
    name: str
    tagline: str = ""
    style: str = "auto"     # auto | stack | orbit | hex
    lockup: bool = True     # True → mark + wordmark; False → mark only


class GenerateLogoSvg(BaseTool):
    name = "generate_logo_svg"
    namespace = "brand"
    description = (
        "Generate an inline-SVG logo for a brand name — a gradient mark (stack/orbit/hex) "
        "with optional wordmark lockup and tagline. Deterministic, no image model. Use for "
        "the primary logo and the favicon-style mark."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        svg = _svg.logo_svg(args.name, tagline=args.tagline,
                            style=args.style, lockup=args.lockup)
        return ToolResult(ok=True, payload=svg)


TOOL = GenerateLogoSvg()

if __name__ == "__main__":
    print(TOOL.run(name="FinPilot", tagline="Ship faster with FinPilot.").payload)
