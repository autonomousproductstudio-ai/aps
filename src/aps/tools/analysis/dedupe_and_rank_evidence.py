"""dedupe_and_rank_evidence — collapse duplicate evidence and rank by signal.

First step of compression: many tools return overlapping items; this dedupes by URL
and near-duplicate title, then ranks by source reliability + content richness.
Deterministic, no network, no LLM.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list

# rough reliability weighting for grounding a market claim
_SOURCE_WEIGHT = {
    "github": 1.0, "stackexchange": 0.95, "arxiv": 0.9, "reddit": 0.85,
    "hackernews": 0.85, "npm": 0.8, "pypi": 0.8, "producthunt": 0.75,
    "wikipedia": 0.7, "jobs": 0.7, "google_trends": 0.7, "web": 0.6,
}


def _norm_url(u: str) -> str:
    u = (u or "").split("?")[0].rstrip("/").lower()
    return re.sub(r"^https?://(www\.)?", "", u)


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)


class DedupeAndRankEvidence(BaseTool):
    name = "dedupe_and_rank_evidence"
    namespace = "analysis"
    description = (
        "Deduplicate a pile of evidence (by URL and near-duplicate title) and rank it by "
        "source reliability and content richness. Run this FIRST during compression to "
        "turn raw, overlapping tool output into a clean ordered set."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        seen_url: set[str] = set()
        seen_title: set[str] = set()
        unique: list[Evidence] = []
        for e in ev:
            key_u = _norm_url(e.url)
            key_t = (e.title or "").strip().lower()[:80]
            if key_u and key_u in seen_url:
                continue
            if key_t and key_t in seen_title:
                continue
            seen_url.add(key_u)
            if key_t:
                seen_title.add(key_t)
            unique.append(e)

        def score(e: Evidence) -> float:
            w = _SOURCE_WEIGHT.get(e.source, 0.5)
            richness = min(len(e.snippet or ""), 300) / 300.0
            has_title = 0.1 if e.title else 0.0
            return w + 0.5 * richness + has_title

        ranked = sorted(unique, key=score, reverse=True)
        return ToolResult(
            ok=True,
            payload=ranked,
            evidence=ranked,
        )


TOOL = DedupeAndRankEvidence()

if __name__ == "__main__":
    import json
    e = [Evidence(source="github", url="https://x/1", title="A", snippet="aaa"),
         Evidence(source="github", url="https://x/1?utm=1", title="A", snippet="aaa"),
         Evidence(source="web", url="https://y/2", title="B", snippet="b")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
