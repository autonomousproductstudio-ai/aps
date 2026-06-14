"""Autonomous debate — a Risk agent vs the build case, resolved to a verdict.

Deterministic, no LLM, no network: transparent rules over the real research brief (+ PRD)
and the Startup Score. The point is *multi-agent reasoning made visible* — the studio
doesn't just generate, it forms an opinion and defends both sides.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.state.models import ResearchReturn, PRD, Severity
from aps.scoring.startup_score import score_startup

_COMPLEX_CUES = ("ml", "machine learning", "realtime", "real-time", "scale", "distributed",
                 "video", "blockchain", "compliance", "hardware", "low-latency", "inference")
_W = {"high": 3.0, "med": 2.0, "low": 1.0}


def _clamp(x: float) -> float:
    return round(max(0.0, min(10.0, x)), 1)


class RiskFlag(BaseModel):
    category: str
    claim: str
    severity: str = "med"          # low | med | high
    sources: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    idea: str
    flags: list[RiskFlag]
    risk_score: float = Field(..., ge=0, le=10)   # higher = riskier


class Debate(BaseModel):
    idea: str
    build_case: list[str]
    risk_case: list[str]
    startup_score: float
    risk_score: float
    verdict: str                    # Build | Pivot | Don't build (yet)
    confidence: float = Field(..., ge=0, le=1)
    rationale: str


def run_risk(research: ResearchReturn, prd: PRD | None = None) -> RiskAssessment:
    """The skeptic agent: build the case AGAINST, grounded in the same evidence."""
    flags: list[RiskFlag] = []
    comps = research.competitors
    pains = research.pain_points
    evidence = research.evidence
    features = prd.features if prd else []
    urls = [e.url for e in evidence if e.url][:4]

    if research.degraded:
        flags.append(RiskFlag(category="Evidence", severity="high",
                              claim="No real market evidence was gathered — the case rests on assumptions."))
    elif len(evidence) < 3:
        flags.append(RiskFlag(category="Evidence", severity="med",
                              claim=f"Thin evidence base ({len(evidence)} items) — demand is under-proven.",
                              sources=urls))

    if "$" not in (research.market_size or ""):
        flags.append(RiskFlag(category="Market", severity="low",
                              claim="No quantified market size (TAM) was found in the evidence."))

    if len(comps) >= 4:
        flags.append(RiskFlag(category="Competition", severity="high",
                              claim=f"Crowded market: {len(comps)} established competitors already exist.",
                              sources=[c.url for c in comps if c.url][:3]))
    elif len(comps) >= 2:
        flags.append(RiskFlag(category="Competition", severity="med",
                              claim=f"{len(comps)} competitors present — differentiation will be required."))

    blob = (research.idea + " " + " ".join(f.title for f in features)).lower()
    cues = [c for c in _COMPLEX_CUES if c in blob]
    if cues:
        flags.append(RiskFlag(category="Technical", severity="med",
                              claim=f"High technical risk: {', '.join(sorted(set(cues))[:4])}."))

    if not any(c.pricing for c in comps):
        flags.append(RiskFlag(category="Monetization", severity="med",
                              claim="Monetization unproven — no competitor pricing observed."))

    if pains and not any(p.severity == Severity.HIGH for p in pains):
        flags.append(RiskFlag(category="Demand", severity="med",
                              claim="Pain points are mild (no high-severity pain) — weak pull."))

    risk = _clamp(sum(_W.get(f.severity, 2.0) for f in flags) * 1.1)
    return RiskAssessment(idea=research.idea, flags=flags, risk_score=risk)


def run_debate(research: ResearchReturn, prd: PRD | None = None) -> Debate:
    """Weigh the build case against the Risk agent and return a verdict."""
    score = score_startup(research, prd)
    risk = run_risk(research, prd)
    comps = research.competitors
    evidence = research.evidence

    build: list[str] = []
    high_pains = [p.text for p in research.pain_points if p.severity == Severity.HIGH]
    if high_pains:
        build.append(f"Real, severe pain exists: \"{high_pains[0]}\".")
    ws = next((d.score for d in score.dimensions if d.name == "Competitive Whitespace"), 5)
    if ws >= 6:
        build.append(f"Room to differentiate — only {len(comps)} competitor(s) found.")
    if "$" in (research.market_size or ""):
        build.append(f"Quantified market: {research.market_size[:80]}.")
    if any(c.pricing for c in comps):
        build.append("Clear monetization path — competitors already charge for this.")
    if evidence:
        build.append(f"Grounded in {len(evidence)} evidence items across "
                     f"{len({e.source for e in evidence})} sources.")
    if not build:
        build.append("Limited positive signal — proceed only on conviction.")

    risk_case = [f"[{f.severity.upper()}] {f.category}: {f.claim}" for f in risk.flags] \
        or ["No material risks flagged."]

    s, r = score.overall, risk.risk_score
    if s >= 7.0 and r <= 4.0:
        verdict = "Build"
    elif s >= 5.5 and r <= 6.5:
        verdict = "Pivot / de-risk first"
    else:
        verdict = "Don't build (yet)"
    confidence = round(min(1.0, 0.35 + min(len(evidence), 20) * 0.03), 2)
    rationale = (f"Startup Score {s}/10 vs Risk {r}/10 → {verdict}. "
                 f"{len(risk.flags)} risk flag(s); {len(build)} point(s) for.")

    return Debate(idea=research.idea, build_case=build, risk_case=risk_case,
                  startup_score=s, risk_score=r, verdict=verdict,
                  confidence=confidence, rationale=rationale)


if __name__ == "__main__":
    import json
    from aps.state.models import Competitor, PainPoint, Evidence
    r = ResearchReturn(
        idea="A B2B SaaS for resume screening",
        market_size="TAM ~$3B (cited)",
        competitors=[Competitor(name="Acme", pricing="$49/mo", features=["x"])],
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH)],
        evidence=[Evidence(source="github", url="https://g/1", title="t", snippet="s")],
    )
    print(json.dumps(run_debate(r).model_dump(), indent=2))
