"""validate_with_sources — keep only evidence that is properly source-grounded.

Second compression step: drop items lacking a well-formed source URL or any substance,
so every downstream claim traces back to something checkable. Structural validation by
default (offline-safe); no network call.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list

_URL = re.compile(r"^https?://[^\s/]+\.[^\s/]+", re.IGNORECASE)


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    min_snippet_len: int = Field(10, ge=0, le=200)


class ValidateWithSources(BaseTool):
    name = "validate_with_sources"
    namespace = "analysis"
    description = (
        "Filter evidence down to items that are genuinely source-grounded: a well-formed "
        "http(s) URL and non-trivial content. Run AFTER dedupe_and_rank to ensure every "
        "claim that reaches the brief is traceable to a real source."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        valid: list[Evidence] = []
        dropped = 0
        for e in ev:
            if _URL.match(e.url or "") and len((e.snippet or "").strip()) >= args.min_snippet_len:
                valid.append(e)
            else:
                dropped += 1
        return ToolResult(
            ok=True,
            payload=valid,
            evidence=valid,
            error=None if not dropped else f"dropped {dropped} ungrounded item(s)",
        )


TOOL = ValidateWithSources()

if __name__ == "__main__":
    import json
    e = [Evidence(source="web", url="https://x.com/a", title="A", snippet="real content here"),
         Evidence(source="web", url="not-a-url", title="B", snippet="x")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
