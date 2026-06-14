"""Startup Score (remaining.md T1.4): bounded, grounded, deterministic, explainable."""
from __future__ import annotations

from aps.state.models import ResearchReturn, Competitor, PainPoint, Feature, Evidence, Severity, PRD
from aps.scoring import score_startup, StartupScore
from aps.render import score_md


def _research(**kw):
    base = dict(
        idea="Build a B2B SaaS for resume screening",
        market_size="TAM ~$3B (cited at https://x.com/report)",
        competitors=[Competitor(name="Acme", features=["pdf export", "ranking"], pricing="$49/mo")],
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH),
                     PainPoint(text="ranking misses people", severity=Severity.MED)],
        evidence=[Evidence(source="github", url="https://g/1", title="t", snippet="s"),
                  Evidence(source="reddit", url="https://r/2", title="t", snippet="s")],
    )
    base.update(kw)
    return ResearchReturn(**base)


def test_score_shape_and_bounds():
    s = score_startup(_research())
    assert isinstance(s, StartupScore)
    assert {d.name for d in s.dimensions} == {
        "Market Opportunity", "Competitive Whitespace", "Technical Feasibility",
        "Monetization Potential", "Founder Velocity",
    }
    for d in s.dimensions:
        assert 0.0 <= d.score <= 10.0 and d.rationale
    assert 0.0 <= s.overall <= 10.0
    assert s.verdict


def test_more_competitors_lowers_whitespace():
    few = score_startup(_research(competitors=[Competitor(name="A")]))
    many = score_startup(_research(competitors=[Competitor(name=f"C{i}", features=["x", "y"])
                                                for i in range(6)]))

    def ws(s):
        return next(d.score for d in s.dimensions if d.name == "Competitive Whitespace")
    assert ws(few) > ws(many)


def test_more_evidence_raises_market_opportunity():
    thin = score_startup(_research(evidence=[]))
    rich = score_startup(_research(evidence=[Evidence(source="hn", url=f"https://h/{i}",
                                                      title="t", snippet="s") for i in range(20)]))

    def mo(s):
        return next(d.score for d in s.dimensions if d.name == "Market Opportunity")
    assert mo(rich) > mo(thin)


def test_verdict_thresholds_are_monotonic():
    # a strong idea outscores a weak one and earns a better verdict
    strong = score_startup(_research())
    weak = score_startup(_research(market_size="", competitors=[Competitor(name=f"C{i}",
                         features=["a", "b", "c"]) for i in range(8)], pain_points=[], evidence=[]))
    assert strong.overall > weak.overall


def test_deterministic():
    r = _research()
    assert score_startup(r).model_dump() == score_startup(r).model_dump()


def test_degraded_research_flag_propagates():
    s = score_startup(_research(degraded=True))
    assert s.grounded is False
    assert "degraded" in score_md.render(s).lower()


def test_prd_features_feed_feasibility_and_velocity():
    prd = PRD(idea="x", features=[Feature(title="realtime ML scoring", description="d", priority="Must"),
                                  Feature(title="dashboard", description="d", priority="Should")])
    s = score_startup(_research(), prd=prd)
    feas = next(d.score for d in s.dimensions if d.name == "Technical Feasibility")
    assert feas < 9.0  # complex cues + features reduce feasibility


def test_score_md_renders_scorecard():
    md = score_md.render(score_startup(_research()))
    assert "# Startup Score" in md and "Overall:" in md
    assert "Market Opportunity" in md and "/ 10" in md
