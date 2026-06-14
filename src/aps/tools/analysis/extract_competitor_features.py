"""extract_competitor_features — pull feature-like claims out of evidence.

Scans for sentences describing capabilities ("supports X", "integrates with Y",
"offers Z") and returns them as a deduped feature list. Feeds build_competitor_matrix.
Deterministic cue-phrase pass, no LLM.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list, evidence_text

_CUES = ("support", "integrat", "offer", "feature", "allow", "enable", "provide",
         "export", "import", "sync", "automat", "dashboard", "api", "real-time",
         "collaborat", "template", "analytics", "search", "free tier")
_SPLIT = re.compile(r"[.!?\n;]")


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    max_features: int = Field(20, ge=1, le=60)


class ExtractCompetitorFeatures(BaseTool):
    name = "extract_competitor_features"
    namespace = "analysis"
    description = (
        "Extract capability/feature claims (e.g. 'supports X', 'integrates with Y') from "
        "evidence about competing products, as a deduped list. Use before "
        "build_competitor_matrix to know what features exist in the space."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        features: list[str] = []
        seen: set[str] = set()
        for e in ev:
            for sent in _SPLIT.split(evidence_text(e)):
                s = sent.strip()
                low = s.lower()
                if 8 <= len(s) <= 160 and any(c in low for c in _CUES):
                    key = low[:60]
                    if key not in seen:
                        seen.add(key)
                        features.append(s)
                if len(features) >= args.max_features:
                    break
            if len(features) >= args.max_features:
                break
        return ToolResult(ok=True, payload=features, evidence=ev)


TOOL = ExtractCompetitorFeatures()

if __name__ == "__main__":
    import json
    e = [Evidence(source="web", url="https://x", title="Acme",
                  snippet="Acme supports PDF export and integrates with Slack. Offers a free tier.")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
