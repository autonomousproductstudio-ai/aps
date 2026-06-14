"""Funding tools (Launch Studio Phase 3): deck outline, grounded financials, roadmap."""
from __future__ import annotations

from aps.tools.funding.generate_pitch_deck_outline import TOOL as DECK
from aps.tools.funding.generate_financial_projections import TOOL as FIN
from aps.tools.funding.generate_fundraising_roadmap import TOOL as ROADMAP
from aps.tools.funding import _finance


def test_registry_exposes_funding_namespace():
    from aps.tools.registry import load_registry
    reg = load_registry()
    assert len(reg["funding"]) == 3
    assert sum(len(v) for v in reg.values()) == 69


def test_parse_tam_picks_largest_figure():
    assert _finance.parse_tam("~$3B ATS market, SOM $5M") == 3_000_000_000
    assert _finance.parse_tam("no money here") is None
    assert _finance.fmt_usd(3_000_000_000) == "$3.0B"
    assert _finance.fmt_usd(120_000) == "$120.0K"


def test_infra_monthly_vs_annual():
    assert _finance.annual_infra("$400/mo") == 4800
    assert _finance.annual_infra("$10,000 per year") == 10000
    assert _finance.annual_infra("") == 6000          # floor when unparseable


def test_projection_is_grounded_and_deterministic():
    a = FIN.run(market_size="~$3B market", infra_cost="$400/mo").payload
    b = FIN.run(market_size="~$3B market", infra_cost="$400/mo").payload
    assert a == b
    assert len(a["years"]) == 3
    assert a["years"][0]["customers"] == 120 and a["years"][2]["customers"] == 900
    assert a["tam"] == 3_000_000_000
    # revenue grows with the customer ramp
    revs = [y["revenue"] for y in a["years"]]
    assert revs[0] < revs[1] < revs[2]
    assert any("NOT a forecast" in n for n in a["notes"])


def test_deck_has_standard_slides_grounded_in_inputs():
    from aps.state.models import PainPoint, Competitor, Feature
    deck = DECK.run(company_name="Habitly", idea="a privacy-first habit tracker",
                    market_size="~$1.2B market",
                    pain_points=[PainPoint(text="can't find a private tracker")],
                    competitors=[Competitor(name="Streaks")],
                    features=[Feature(title="Streak tracking", description="x")]).payload
    titles = [s["title"] for s in deck]
    assert "Problem" in titles and "Market" in titles and "The Ask" in titles
    problem = next(s for s in deck if s["title"] == "Problem")
    assert "can't find a private tracker" in problem["bullets"]
    market = next(s for s in deck if s["title"] == "Market")
    assert any("$1.2B" in b for b in market["bullets"])


def test_roadmap_has_three_rounds_and_use_of_funds():
    out = ROADMAP.run(company_name="Habitly",
                      roadmap="Sprint 1: auth\nSprint 2: tracking").payload
    rounds = [r["round"] for r in out["rounds"]]
    assert rounds == ["Pre-seed", "Seed", "Series A"]
    assert sum(u["pct"] for u in out["use_of_funds"]) == 100
    assert "auth" in out["rounds"][0]["milestones"].lower()
