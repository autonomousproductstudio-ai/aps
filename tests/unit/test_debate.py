"""T2.3 — Autonomous Debate: grounded risk flags, build case, verdict logic, determinism."""
from __future__ import annotations

from aps.state.models import ResearchReturn, Competitor, PainPoint, Evidence, Severity, PRD, Feature
from aps.debate import run_risk, run_debate, RiskAssessment, Debate
from aps.render import debate_md


def _strong():
    return ResearchReturn(
        idea="A B2B SaaS for resume screening",
        market_size="TAM ~$3B (cited at https://x.com/r)",
        competitors=[Competitor(name="Acme", url="https://acme.io", pricing="$49/mo",
                                features=["pdf export"])],
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH)],
        evidence=[Evidence(source=s, url=f"https://{s}/1", title="t", snippet="s")
                  for s in ("github", "reddit", "hackernews", "stackexchange")],
    )


def _weak():
    return ResearchReturn(
        idea="A realtime ML video platform",
        market_size="",
        competitors=[Competitor(name=f"C{i}", features=["a", "b"]) for i in range(5)],
        pain_points=[PainPoint(text="minor annoyance", severity=Severity.LOW)],
        evidence=[],
        degraded=True,
    )


def test_risk_flags_are_grounded_and_scored():
    ra = run_risk(_weak())
    assert isinstance(ra, RiskAssessment)
    cats = {f.category for f in ra.flags}
    assert {"Competition", "Monetization"} <= cats     # 5 comps, no pricing
    assert any(f.category == "Evidence" and f.severity == "high" for f in ra.flags)  # degraded
    assert ra.risk_score > run_risk(_strong()).risk_score


def test_strong_idea_builds_weak_idea_does_not():
    strong = run_debate(_strong())
    weak = run_debate(_weak())
    assert isinstance(strong, Debate)
    assert strong.verdict == "Build"
    assert weak.verdict == "Don't build (yet)"
    assert strong.startup_score > weak.startup_score
    assert strong.risk_score < weak.risk_score


def test_build_case_cites_real_positives():
    d = run_debate(_strong())
    joined = " ".join(d.build_case).lower()
    assert "pain" in joined and "evidence" in joined
    assert 0.0 <= d.confidence <= 1.0


def test_technical_risk_flag_from_complex_idea():
    ra = run_risk(_weak(), prd=PRD(idea="x", features=[Feature(title="realtime ml scoring", description="d")]))
    assert any(f.category == "Technical" for f in ra.flags)


def test_deterministic():
    r = _strong()
    assert run_debate(r).model_dump() == run_debate(r).model_dump()


def test_debate_md_has_both_sides_and_verdict():
    md = debate_md.render(run_debate(_strong()))
    assert "Verdict:" in md and "case FOR" in md and "case AGAINST" in md
