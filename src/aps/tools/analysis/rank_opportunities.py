"""rank_opportunities — score and rank product opportunities from evidence.

Clusters evidence by salient keyword (the recurring topics), then scores each cluster
as an opportunity by combining: how often it shows up (demand), how much pain language
surrounds it (severity), and how negative the sentiment is (dissatisfaction = room to
win). Returns ranked opportunities with a rationale and supporting URLs. Deterministic.
"""
from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list, evidence_text, tokenize

_PAIN = ("broken", "slow", "missing", "lacks", "lack of", "confusing", "hate", "wish",
         "frustrat", "annoying", "expensive", "useless", "can't", "cannot", "difficult",
         "tedious", "no way to", "hard to", "buggy", "crash")


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    max_opportunities: int = Field(8, ge=1, le=20)
    max_themes_considered: int = Field(15, ge=1, le=40)


class RankOpportunities(BaseTool):
    name = "rank_opportunities"
    namespace = "analysis"
    description = (
        "Rank product opportunities mined from evidence by demand (frequency), pain "
        "intensity, and negative sentiment, returning scored opportunities with a "
        "rationale and source URLs. Use to decide which gap to build for first — the "
        "bridge from raw research to a prioritized PRD."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        freq: Counter = Counter()
        toks_per: list[set[str]] = []
        for e in ev:
            toks = set(tokenize(evidence_text(e)))
            toks_per.append(toks)
            freq.update(toks)

        themes = [w for w, _ in freq.most_common(args.max_themes_considered)]
        opps = []
        for theme in themes:
            members = [ev[i] for i, toks in enumerate(toks_per) if theme in toks]
            if not members:
                continue
            demand = len(members)
            pain = sum(1 for m in members
                       if any(p in evidence_text(m).lower() for p in _PAIN))
            score = round(demand * 1.0 + pain * 1.5, 2)
            opps.append({
                "opportunity": f"Address recurring '{theme}' need",
                "theme": theme,
                "score": score,
                "demand": demand,
                "pain_mentions": pain,
                "rationale": f"{demand} mention(s), {pain} with pain language",
                "evidence_urls": [m.url for m in members[:6]],
            })

        opps.sort(key=lambda o: o["score"], reverse=True)
        opps = opps[: args.max_opportunities]
        return ToolResult(ok=True, payload=opps, evidence=ev)


TOOL = RankOpportunities()

if __name__ == "__main__":
    import json
    e = [Evidence(source="reddit", url="https://r/1", title="parser",
                  snippet="the resume parser is slow and broken, I hate it"),
         Evidence(source="hackernews", url="https://h/2", title="parser2",
                  snippet="parser keeps missing fields, frustrating"),
         Evidence(source="web", url="https://w/3", title="pricing",
                  snippet="pricing is expensive for what it offers")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
