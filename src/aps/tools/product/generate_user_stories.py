"""generate_user_stories — turn personas + pains into 'As a … I want … so that …' stories.

Deterministic templating over the typed inputs; the value is structure and traceability,
not prose generation. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Persona, PainPoint
from aps.tools.analysis._text import pain_to_feature_title


class Args(BaseModel):
    personas: list[Persona] = Field(default_factory=list)
    pain_points: list[PainPoint] = Field(default_factory=list)
    max_stories: int = Field(12, ge=1, le=40)


class GenerateUserStories(BaseTool):
    name = "generate_user_stories"
    namespace = "product"
    description = (
        "Write user stories in 'As a <role>, I want <capability>, so that <benefit>' "
        "form from personas and pain points. Use after generate_personas to make the "
        "needs concrete and testable before prioritizing features."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        stories: list[str] = []
        seen: set[tuple[str, str]] = set()
        roles = [p.role or p.name for p in args.personas] or ["user"]
        # Phrase the WANT as a clean capability (the same noun-phrase used for features), not a
        # quoted raw pain — "I want bulk delete" reads as a story; "I want to overcome 'no way to
        # bulk delete'" does not. Dedupe so two pains that share a capability don't repeat.
        pains = [p.text for p in args.pain_points] or [""]
        for i, pain in enumerate(pains):
            role = roles[i % len(roles)]
            cap = pain_to_feature_title(pain) if pain.strip() else "my core task"
            cap = (cap[0].lower() + cap[1:]) if cap else "my core task"
            key = (role.lower(), cap.lower())
            if key in seen:
                continue
            seen.add(key)
            stories.append(
                f"As a {role}, I want {cap}, so that I can get my job done without friction."
            )
            if len(stories) >= args.max_stories:
                break
        return ToolResult(ok=True, payload=stories)


TOOL = GenerateUserStories()

if __name__ == "__main__":
    import json
    out = TOOL.run(personas=[Persona(name="Recruiter", role="recruiter").model_dump()],
                   pain_points=[PainPoint(text="parser drops PDFs").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
