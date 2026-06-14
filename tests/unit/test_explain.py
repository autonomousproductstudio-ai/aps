"""T2.5 — Explain-Why: every feature traced to its pain/competitor/evidence + confidence."""
from __future__ import annotations

from aps.state.models import PRD, ResearchReturn, Competitor, Evidence, Feature
from aps.explain import explain_prd, Explanation
from aps.render import explain_md


def _setup():
    ev = [Evidence(source="github", url="https://github.com/x/1", title="parser bug",
                   snippet="the resume parser drops valid pdf files"),
          Evidence(source="reddit", url="https://reddit.com/r/2", title="ranking",
                   snippet="candidate ranking quality is poor")]
    prd = PRD(
        idea="AI resume screening",
        features=[Feature(title="Solve: parser drops PDFs", description="reliable pdf parsing", priority="Must"),
                  Feature(title="Table stakes: ranking", description="rank candidates", priority="Should"),
                  Feature(title="Differentiator: analytics", description="dashboards", priority="Could")],
        sources=ev,
    )
    research = ResearchReturn(
        idea="AI resume screening", evidence=ev,
        competitors=[Competitor(name="Acme", features=["ranking", "analytics"])],
    )
    return prd, research


def test_explains_every_feature():
    prd, research = _setup()
    x = explain_prd(prd, research)
    assert isinstance(x, Explanation)
    assert len(x.features) == 3
    assert 0.0 <= x.overall_confidence <= 1.0
    for fe in x.features:
        assert fe.why and 0.0 <= fe.confidence <= 1.0


def test_pain_feature_cites_matching_evidence():
    prd, research = _setup()
    pdf = next(f for f in explain_prd(prd, research).features if "parser" in f.feature_title.lower())
    assert "pain" in pdf.why.lower()
    assert any("github.com/x/1" in e.url for e in pdf.evidence)   # matched the parser source


def test_competitor_feature_names_its_inspiration():
    prd, research = _setup()
    feats = {f.feature_title: f for f in explain_prd(prd, research).features}
    assert feats["Table stakes: ranking"].inspired_by == "Acme"
    assert feats["Differentiator: analytics"].inspired_by == "Acme"


def test_confidence_rewards_evidence_and_must_priority():
    prd, research = _setup()
    x = explain_prd(prd, research)
    must = next(f for f in x.features if f.priority == "Must")
    could = next(f for f in x.features if f.priority == "Could")
    assert must.confidence >= could.confidence


def test_works_without_research_using_prd_sources():
    prd, _ = _setup()
    x = explain_prd(prd)               # no research -> falls back to prd.sources
    assert len(x.features) == 3


def test_deterministic_and_renders():
    prd, research = _setup()
    assert explain_prd(prd, research).model_dump() == explain_prd(prd, research).model_dump()
    md = explain_md.render(explain_prd(prd, research))
    assert "Explain-Why" in md and "confidence" in md.lower() and "Acme" in md
