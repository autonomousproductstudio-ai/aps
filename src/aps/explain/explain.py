"""Explain-Why — trace every PRD feature back to its evidence, competitor, and confidence.

Deterministic, no LLM: token-overlap matching against the gathered evidence (the same
grounding primitive the PRD renderer uses) + the feature's own provenance encoded by
`prioritize_features` ("Solve:" → a pain, "Table stakes:"/"Differentiator:" → a competitor).
The point is *trust*: a judge can click "why" on any feature and see real sources.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.state.models import PRD, ResearchReturn, Evidence, Feature


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", (text or "").lower())}


def _matching(text: str, sources: list[Evidence], limit: int = 3) -> list[Evidence]:
    want = _tokens(text)
    if not want:
        return []
    scored = []
    for e in sources:
        overlap = len(want & _tokens(f"{e.title or ''} {e.snippet or ''}"))
        if overlap:
            scored.append((overlap, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


class FeatureExplanation(BaseModel):
    feature_title: str
    priority: str
    why: str
    inspired_by: str | None = None          # competitor name, when applicable
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)


class Explanation(BaseModel):
    idea: str
    features: list[FeatureExplanation]
    overall_confidence: float = Field(..., ge=0, le=1)


def _explain_one(feature: Feature, research: ResearchReturn | None,
                 sources: list[Evidence], competitors) -> FeatureExplanation:
    title = feature.title
    low = title.lower()
    matched = _matching(f"{title} {feature.description}", sources)
    inspired_by = None

    if low.startswith("solve:"):
        pain = title.split(":", 1)[1].strip()
        why = f'Addresses the user pain "{pain}"'
    elif low.startswith("table stakes:") or low.startswith("differentiator:"):
        cap = title.split(":", 1)[1].strip()
        for c in competitors:
            if any(cap.lower() in f.lower() or f.lower() in cap.lower() for f in c.features):
                inspired_by = c.name
                break
        kind = "Table-stakes" if low.startswith("table") else "Differentiator"
        why = f"{kind} capability" + (f" inspired by {inspired_by}" if inspired_by
                                      else " seen across the competitive set")
    else:
        why = "Derived from the research findings"

    if matched:
        why += f", grounded in {len(matched)} source(s)"

    confidence = round(min(1.0,
                           0.3 + 0.15 * len(matched)
                           + (0.2 if inspired_by else 0.0)
                           + (0.1 if feature.priority == "Must" else 0.0)), 2)
    return FeatureExplanation(feature_title=title, priority=feature.priority, why=why,
                              inspired_by=inspired_by, evidence=matched, confidence=confidence)


def explain_prd(prd: PRD, research: ResearchReturn | None = None) -> Explanation:
    sources = (research.evidence if research and research.evidence else None) or prd.sources
    competitors = research.competitors if research else []
    feats = [_explain_one(f, research, sources, competitors) for f in prd.features]
    overall = round(sum(f.confidence for f in feats) / len(feats), 2) if feats else 0.0
    return Explanation(idea=prd.idea, features=feats, overall_confidence=overall)


if __name__ == "__main__":
    import json
    from aps.state.models import Competitor
    prd = PRD(idea="resume screening",
              features=[Feature(title="Solve: parser drops PDFs", description="fix parsing", priority="Must"),
                        Feature(title="Table stakes: ranking", description="rank", priority="Should")],
              sources=[Evidence(source="github", url="https://g/1", title="parser",
                                snippet="the resume parser drops pdf files")])
    r = ResearchReturn(idea="resume screening",
                       competitors=[Competitor(name="Acme", features=["ranking"])],
                       evidence=prd.sources)
    print(json.dumps(explain_prd(prd, r).model_dump(), indent=2, default=str))
