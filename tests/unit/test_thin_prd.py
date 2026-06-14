"""W3 — the feature floor prevents thin PRDs without fabricating features."""
from __future__ import annotations

from aps.state.models import PainPoint, Competitor, Severity, ResearchReturn, Evidence
from aps.tools.product.prioritize_features import TOOL as prioritize
from aps.agents.product.agent import run_product


def test_three_pains_yield_three_features():
    pains = [PainPoint(text=f"pain {i}", severity=Severity.HIGH) for i in range(3)]
    feats = prioritize.run(pain_points=pains, competitors=[]).payload
    assert len(feats) >= 3


def test_floor_promotes_competitor_signal_when_thin():
    # one pain but a rich competitive set -> floor lifts to >=3 from REAL competitor features
    pains = [PainPoint(text="parser drops PDFs", severity=Severity.HIGH)]
    comps = [Competitor(name="A", features=["pdf export", "slack sync"]),
             Competitor(name="B", features=["analytics dashboard"])]
    feats = prioritize.run(pain_points=pains, competitors=comps).payload
    assert len(feats) >= 3
    # every promoted feature traces to real competitor wording (no fabrication)
    promoted = [f for f in feats if f.title.startswith("Differentiator:")]
    pool_lower = " ".join(f.lower() for c in comps for f in c.features)
    assert all(f.title.split(":", 1)[1].strip().lower() in pool_lower for f in promoted)


def test_no_signal_stays_honestly_short():
    # one pain, no competitors -> cannot reach the floor honestly; stays at 1 (not faked)
    feats = prioritize.run(pain_points=[PainPoint(text="only pain")], competitors=[]).payload
    assert len(feats) == 1


def test_floor_never_exceeds_max():
    pains = [PainPoint(text=f"pain {i}") for i in range(2)]
    comps = [Competitor(name="A", features=[f"feat{i}" for i in range(20)])]
    feats = prioritize.run(pain_points=pains, competitors=comps, max_features=5).payload
    assert len(feats) <= 5


def test_product_agent_prd_meets_floor_with_real_research():
    research = ResearchReturn(
        idea="resume screening",
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH)],
        competitors=[Competitor(name="A", features=["pdf export", "ranking"]),
                     Competitor(name="B", features=["analytics"])],
        evidence=[Evidence(source="github", url="https://g/1", title="t", snippet="s")],
    )
    prd = run_product(research)
    assert len(prd.features) >= 3
