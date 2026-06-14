"""Adversarial hardening: the Startup Score must not reward ABSENCE of evidence.

Before this, an empty / degraded research brief scored ~7/10 "Promising — worth a focused MVP"
because Competitive Whitespace maxed at 10 (no competitors found) and Founder Velocity sat at 9
(no features defined). A judge typing a nonsense idea would get an encouraging verdict. These
tests pin the grounding gate: thin/degraded evidence yields a low, honestly-captioned score.
"""
from __future__ import annotations

from aps.state.models import ResearchReturn, Competitor, PainPoint, Feature, Evidence, Severity, PRD
from aps.scoring import score_startup


def _dim(s, name):
    return next(d.score for d in s.dimensions if d.name == name)


def _empty():
    return ResearchReturn(idea="a vague idea with no research behind it")


def test_empty_research_is_not_promising():
    s = score_startup(_empty())
    assert s.overall <= 5.5                       # not "Promising" (>=6.5) or "Strong" (>=8.0)
    low = s.verdict.lower()
    assert "build it" not in low and "promising" not in low
    assert "evidence" in low                      # says WHY it's low


def test_whitespace_not_maxed_without_competitor_data():
    # no competitors found + thin evidence ⇒ "unknown", NOT maximum opportunity
    s = score_startup(ResearchReturn(idea="x", evidence=[
        Evidence(source="reddit", url="https://r/1", title="t", snippet="s")]))
    assert _dim(s, "Competitive Whitespace") < 8.0


def test_well_researched_greenfield_beats_unresearched():
    # genuine greenfield (lots of evidence, still no competitors) should out-rank no-data
    ev = [Evidence(source="hn", url=f"https://h/{i}", title="t", snippet="s") for i in range(20)]
    researched = score_startup(ResearchReturn(idea="x", evidence=ev))
    unresearched = score_startup(ResearchReturn(idea="x"))
    assert _dim(researched, "Competitive Whitespace") > _dim(unresearched, "Competitive Whitespace")


def test_no_prd_velocity_is_neutral_not_max():
    s = score_startup(_empty())                   # no PRD ⇒ unscoped, not "ships fast"
    assert _dim(s, "Founder Velocity") == 6.0


def test_velocity_rewards_small_prd_over_no_prd():
    prd = PRD(idea="x", features=[Feature(title="one thing", description="d", priority="Must")])
    scoped = score_startup(_empty(), prd=prd)
    assert _dim(scoped, "Founder Velocity") > 6.0  # a tight, defined scope beats "unknown"


def test_degraded_brief_caps_overall_even_with_rich_stub_data():
    # a DEGRADED run carries stub fixtures that LOOK rich — they must not earn a confident score
    rich_stub = ResearchReturn(
        idea="Build a B2B SaaS for X",
        market_size="TAM ~$5B (cited)",
        competitors=[Competitor(name="Acme", features=["a", "b"], pricing="$49/mo")],
        pain_points=[PainPoint(text="p", severity=Severity.HIGH)],
        evidence=[Evidence(source="github", url=f"https://g/{i}", title="t", snippet="s")
                  for i in range(5)],
        degraded=True,
    )
    s = score_startup(rich_stub)
    assert s.overall <= 4.5 and s.grounded is False
    assert "degraded" in s.verdict.lower() or "evidence" in s.verdict.lower()


def test_grounded_real_idea_can_still_score_well():
    # the gate must not punish a genuinely well-evidenced idea
    s = score_startup(ResearchReturn(
        idea="Build a B2B SaaS for resume screening",
        market_size="TAM ~$3B (cited at https://x/report)",
        competitors=[Competitor(name="Acme", features=["pdf export"], pricing="$49/mo")],
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH),
                     PainPoint(text="ranking misses people", severity=Severity.MED)],
        evidence=[Evidence(source=s_, url=f"https://{s_}/1", title="t", snippet="s")
                  for s_ in ("github", "reddit", "hn", "ph")],
    ))
    assert s.overall >= 5.0 and s.grounded is True
    assert "evidence" not in s.verdict.lower()   # not the thin/degraded caption
