"""cluster_themes — group evidence into recurring themes by shared keywords.

Lightweight keyword-frequency clustering (no embeddings, no LLM): find the most
common salient tokens, treat each as a theme, and bucket evidence under the theme
keyword it mentions most. Gives the agent a map of what topics dominate.
"""
from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list, evidence_text, tokenize


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    max_themes: int = Field(6, ge=1, le=15)


class ClusterThemes(BaseTool):
    name = "cluster_themes"
    namespace = "analysis"
    description = (
        "Cluster evidence into recurring themes by shared keywords and return each theme "
        "with its frequency and supporting URLs. Use to see which topics dominate the "
        "research before extracting pains — a map, not a ranking."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        freq: Counter = Counter()
        toks_per = []
        for e in ev:
            toks = set(tokenize(evidence_text(e)))
            toks_per.append(toks)
            freq.update(toks)
        themes = [w for w, _ in freq.most_common(args.max_themes)]
        clusters = []
        for theme in themes:
            members = [ev[i] for i, toks in enumerate(toks_per) if theme in toks]
            clusters.append({
                "theme": theme,
                "count": len(members),
                "evidence_urls": [m.url for m in members[:8]],
            })
        return ToolResult(ok=True, payload=clusters, evidence=ev)


TOOL = ClusterThemes()

if __name__ == "__main__":
    import json
    e = [Evidence(source="reddit", url="https://r/1", title="parser slow",
                  snippet="resume parser is slow and inaccurate"),
         Evidence(source="hackernews", url="https://h/2", title="pricing",
                  snippet="pricing for these parser tools is too high")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
