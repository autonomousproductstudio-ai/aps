"""Startup Score — grade an idea 0–10 across five evidence-grounded dimensions.

Deterministic, no LLM, no network: a transparent heuristic over the real research brief
(+ optional PRD). Every dimension carries a one-line rationale naming the signals it used,
so the score is explainable (the seed for "Explain-Why", remaining.md T2.5).

Dimensions are framed so **higher is always better** (avoids the ambiguity of raw
"Competition"/"Technical Difficulty" labels — see decision.md D21):
  • Market Opportunity     — demand signals + an explicit market figure
  • Competitive Whitespace — room left by competitors (fewer/weaker ⇒ higher)
  • Technical Feasibility   — how buildable the MVP looks (simpler ⇒ higher)
  • Monetization Potential  — evidence of willingness to pay (competitor pricing, B2B)
  • Founder Velocity        — how fast a focused MVP could ship (smaller scope ⇒ higher)
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.state.models import ResearchReturn, PRD

_COMPLEX_CUES = ("ml", "machine learning", "realtime", "real-time", "scale", "distributed",
                 "video", "blockchain", "compliance", "hardware", "low-latency", "inference")
_B2B_CUES = ("b2b", "saas", "enterprise", "team", "business", "api", "platform", "workflow")


def _clamp(x: float) -> float:
    return round(max(0.0, min(10.0, x)), 1)


class Dimension(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=10)
    rationale: str


class StartupScore(BaseModel):
    idea: str
    dimensions: list[Dimension]
    overall: float = Field(..., ge=0, le=10)
    verdict: str
    grounded: bool = True   # False when computed off a degraded (stub) research brief


def _verdict(overall: float) -> str:
    if overall >= 8.0:
        return "Strong — build it"
    if overall >= 6.5:
        return "Promising — worth a focused MVP"
    if overall >= 5.0:
        return "Proceed with caution"
    return "High risk / crowded — reconsider or pivot"


def score_startup(research: ResearchReturn, prd: PRD | None = None) -> StartupScore:
    comps = research.competitors
    pains = research.pain_points
    evidence = research.evidence
    market_size = research.market_size or ""
    features = prd.features if prd else []

    # Market Opportunity — real demand signal + a cited dollar figure
    has_figure = bool(re.search(r"\$\s?\d", market_size))
    market = _clamp(3.5 + min(len(evidence), 30) * 0.12 + len(pains) * 0.5 + (2.0 if has_figure else 0.0))

    # Competitive Whitespace — fewer/weaker competitors ⇒ more room. BUT absence of competitor
    # evidence is NOT proof of greenfield: distinguish "researched, found few" (high) from
    # "barely researched" (unknown ⇒ neutral). Otherwise an ungrounded idea scores max whitespace.
    if comps:
        intensity = len(comps) * 1.3 + sum(len(c.features) for c in comps) * 0.25
        whitespace = _clamp(10.0 - intensity)
    else:
        whitespace = _clamp(4.0 + min(len(evidence), 20) * 0.15)   # 4.0 (no data) → 7.0 (well-researched)

    # Technical Feasibility — more features / complex cues ⇒ harder to build
    blob = (research.idea + " " + " ".join(f.title for f in features)).lower()
    complexity = len(features) * 0.4 + sum(2.0 for cue in _COMPLEX_CUES if cue in blob)
    feasibility = _clamp(9.0 - complexity)

    # Monetization Potential — competitor pricing = proven willingness to pay; B2B skews up
    priced = sum(1 for c in comps if c.pricing)
    b2b = any(cue in research.idea.lower() for cue in _B2B_CUES)
    monetization = _clamp(4.5 + priced * 1.2 + (1.5 if b2b else 0.0))

    # Founder Velocity — a smaller must-have set ships faster. With no PRD there's no scope to
    # judge, so it's "unknown" (neutral), NOT a free maximum — an idea with zero defined features
    # isn't fast to ship, it's unscoped.
    must = sum(1 for f in features if f.priority == "Must")
    velocity = _clamp(9.0 - must * 0.8 - max(0, len(features) - 6) * 0.3) if features else 6.0

    dims = [
        Dimension(name="Market Opportunity", score=market,
                  rationale=f"{len(evidence)} evidence items, {len(pains)} pains"
                            + ("; explicit market figure cited" if has_figure else "; no explicit TAM figure")),
        Dimension(name="Competitive Whitespace", score=whitespace,
                  rationale=f"{len(comps)} competitor(s); "
                            + ("crowded" if whitespace < 5 else "room to differentiate")),
        Dimension(name="Technical Feasibility", score=feasibility,
                  rationale=f"{len(features)} features"
                            + ("; complex tech cues present" if complexity > len(features) * 0.4 else "; standard stack")),
        Dimension(name="Monetization Potential", score=monetization,
                  rationale=f"{priced} competitor(s) with pricing" + ("; B2B" if b2b else "")),
        Dimension(name="Founder Velocity", score=velocity,
                  rationale=f"{must} must-have feature(s) for v1"),
    ]
    overall = _clamp(sum(d.score for d in dims) / len(dims))

    # GROUNDING GATE — a score is only as credible as the evidence under it. A degraded (stub)
    # brief or near-empty research must NOT yield a confident "build it" verdict; cap the overall
    # and say why. This is what stops a nonsense idea scoring "Promising — worth a focused MVP".
    if research.degraded:
        overall = _clamp(min(overall, 4.5))
        verdict = "Insufficient evidence — research degraded (set an LLM key to ground this)"
    elif len(evidence) < 3 and not comps and not pains:
        overall = _clamp(min(overall, 5.5))
        verdict = "Thin evidence — gather more signal before committing"
    else:
        verdict = _verdict(overall)

    return StartupScore(idea=research.idea, dimensions=dims, overall=overall,
                        verdict=verdict, grounded=not research.degraded)


if __name__ == "__main__":
    import json
    from aps.state.models import Competitor, PainPoint, Evidence, Severity
    r = ResearchReturn(
        idea="Build a B2B SaaS for resume screening",
        market_size="TAM ~$3B (cited at https://x.com/report)",
        competitors=[Competitor(name="Acme", features=["pdf export", "ranking"], pricing="$49/mo")],
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH)],
        evidence=[Evidence(source="github", url="https://g/1", title="t", snippet="s")],
    )
    print(json.dumps(score_startup(r).model_dump(), indent=2))
