"""generate_demo_script — a step-by-step demo walkthrough from features + personas.

Deterministic: opens in a persona's shoes, walks the top features as demo beats, closes
on the resolved pain. Returns the script *string*. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Feature, Persona


class Args(BaseModel):
    idea: str = ""
    features: list[Feature] = Field(default_factory=list)
    personas: list[Persona] = Field(default_factory=list)


class GenerateDemoScript(BaseTool):
    name = "generate_demo_script"
    namespace = "presentation"
    description = (
        "Generate a demo script: open in a persona's shoes, walk the top features as demo "
        "beats, close on the resolved pain. Use to make the pitch tangible in a live "
        "walkthrough."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        who = (args.personas[0].role if args.personas else "the user")
        beats = [f"Step {i+1}: show '{f.title}' — {f.description}"
                 for i, f in enumerate(args.features[:5])]
        if not beats:
            beats = ["Step 1: show the core workflow end to end."]
        script = (
            f"Demo — {args.idea}\n"
            f"Setup: we're {who} facing the core problem.\n"
            + "\n".join(beats)
            + "\nClose: the original pain is resolved in one flow — that's the wedge."
        )
        return ToolResult(ok=True, payload=script)


TOOL = GenerateDemoScript()

if __name__ == "__main__":
    import json
    out = TOOL.run(idea="resume screening",
                   features=[Feature(title="Parse PDFs", description="reliable parsing").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
