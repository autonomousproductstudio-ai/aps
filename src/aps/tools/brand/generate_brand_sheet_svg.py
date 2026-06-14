"""generate_brand_sheet_svg — a shareable brand card (lockup + palette + taglines).

One self-contained SVG suitable for a README hero or a launch slide. Deterministic,
stdlib-only. Returns the SVG *string*.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.brand import _svg


class Args(BaseModel):
    name: str
    tagline: str = ""
    taglines: list[str] = Field(default_factory=list)
    style: str = "auto"


class GenerateBrandSheetSvg(BaseTool):
    name = "generate_brand_sheet_svg"
    namespace = "brand"
    description = (
        "Generate a single shareable brand sheet as inline SVG: the logo lockup, the colour "
        "palette as labelled swatches, and up to three alternate taglines. Use as the "
        "launch-ready brand card."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        svg = _svg.brand_sheet_svg(args.name, args.tagline, args.taglines, style=args.style)
        return ToolResult(ok=True, payload=svg)


TOOL = GenerateBrandSheetSvg()

if __name__ == "__main__":
    print(TOOL.run(name="FinPilot", tagline="Ship faster.",
                   taglines=["a", "b", "c"]).payload[:200])
