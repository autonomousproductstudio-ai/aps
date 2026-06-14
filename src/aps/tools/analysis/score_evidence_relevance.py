"""score_evidence_relevance — relevance gate for the research compression step.

The retrieval loop can surface evidence that merely *mentions a keyword* but has nothing to
do with the product idea (a "YouTube AdBlock" gripe for a "Private Activity Tracker"). Nothing
downstream checks idea-relevance — dedupe ranks by source weight, the noise filter only asks
"does this look like a complaint?" — so off-topic items flow straight into pains/features.

This tool scores each evidence item 0–1 for relevance to the idea by deterministic lexical
overlap (the idea's distinctive noun stems vs. the evidence's title+snippet stems), tags it on
`Evidence.relevance`, and — when `min_score` is given — drops items below it. Pure, offline,
no LLM (an optional LLM refinement lives at the agent layer, `research/_relevance.py`).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import tokenize, evidence_text, as_evidence_list

# Idea-independent off-domain spam that keyword search drags in: a snippet dominated by these,
# with no real idea overlap, is junk no matter the idea ("Stake bonus cannot be reached", random
# sales/recruiting jobs). Hard-rejected so it never reaches pain extraction.
_JUNK = {"sales", "bonus", "stake", "freelance", "writer", "recruiter", "hiring", "specialist",
         "rater", "analyst", "assistant", "contractor", "salary", "deposit", "withdrawal",
         "payment", "currency", "casino", "betting", "gambling", "loan", "mortgage", "crypto",
         "forex", "trading", "invoice", "payroll", "vacancy", "intern", "internship"}


def _related(a: str, b: str) -> bool:
    """Morphology-robust token match: equal, or a shared prefix ≥4 chars covering ≥60% of the
    shorter token — so private~privacy, tracker~tracking~track, activity~activities all match
    (a plain singular-stem set-intersection misses these). Lifted from the relevance_gate design."""
    if a == b:
        return True
    n = min(len(a), len(b))
    if n < 4:
        return False
    p = 0
    while p < n and a[p] == b[p]:
        p += 1
    return p >= 4 and p >= 0.6 * n


def idea_profile(idea: str) -> set[str]:
    """The set of idea key terms used as the relevance target (empty ⇒ don't gate)."""
    return set(tokenize(idea))


def relevance_score(idea_terms: set[str], e) -> float:
    """0–1 relevance of one Evidence to the idea: fraction of idea terms that have a MORPHOLOGY-
    related token in the evidence text, plus a small bonus when the overlap reaches the title.
    No idea terms ⇒ 1.0 (a degenerate/all-stopword idea must not gate everything out). An item
    dominated by off-domain junk with no real overlap scores 0 regardless."""
    if not idea_terms:
        return 1.0
    ev_toks = tokenize(evidence_text(e))
    if not ev_toks:
        return 0.0
    hits = sum(1 for t in idea_terms if any(_related(t, w) for w in ev_toks))
    base = hits / len(idea_terms)
    title = (e.get("title") if isinstance(e, dict) else getattr(e, "title", "")) or ""
    title_toks = tokenize(title)
    bonus = 0.1 if any(_related(t, w) for t in idea_terms for w in title_toks) else 0.0
    # Junk hard-reject: weak idea overlap AND off-domain spam tokens present ⇒ not relevant.
    if base < 0.34 and any(w in _JUNK for w in ev_toks):
        return 0.0
    return round(min(1.0, base + bonus), 3)


class Args(BaseModel):
    idea: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    min_score: float | None = Field(
        default=None, description="If set, drop evidence scoring below this (0–1) after tagging.")


class ScoreEvidenceRelevance(BaseTool):
    name = "score_evidence_relevance"
    namespace = "analysis"
    description = (
        "Score each evidence item 0–1 for relevance to the product idea (deterministic lexical "
        "overlap) and tag it on `relevance`; optionally drop items below `min_score`. Run during "
        "compression to reject off-topic evidence BEFORE pain/competitor/market extraction."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        prof = idea_profile(args.idea)
        for e in ev:
            e.relevance = relevance_score(prof, e)
        out = ev
        if args.min_score is not None:
            out = [e for e in ev if (e.relevance or 0.0) >= args.min_score]
        return ToolResult(ok=True, payload=out, evidence=out)


TOOL = ScoreEvidenceRelevance()

if __name__ == "__main__":
    import json
    idea = "Private Activity Tracker"
    e = [Evidence(source="web", url="https://x/1", title="Best activity trackers",
                  snippet="this activity tracker leaks location data to advertisers"),
         Evidence(source="github", url="https://x/2", title="YouTube AdBlock",
                  snippet="the adblock popup is missing in the new youtube ui")]
    out = TOOL.run(idea=idea, evidence=[x.model_dump() for x in e], min_score=0.15)
    print(json.dumps([{"title": x.title, "relevance": x.relevance} for x in out.evidence], indent=2))
