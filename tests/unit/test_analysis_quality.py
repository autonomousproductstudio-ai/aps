"""Analysis-layer quality guards: no job/market-report contamination, real competitors
surfaced, and demand evidence yields pains. Regression cover for the live failures where
job postings became PRD features and pain extraction returned nothing.
"""
from __future__ import annotations

from aps.tools.analysis import build_competitor_matrix as cm
from aps.tools.analysis import extract_pain_points as pp
from aps.tools.product import prioritize_features as pf
from aps.tools.analysis._sources import evidence_kind, is_extractable
from aps.state.models import Evidence, Competitor


# ── source-type tagging + the extraction gate ──────────────────────────────
def test_evidence_kind_classifies_each_source_type():
    cases = {
        "job": Evidence(source="jobs", url="https://remotive.com/job/1", title="Copywriter", snippet="role"),
        "market_report": Evidence(source="web", url="https://x.com/r", title="Report",
                                  snippet="Market size expected to reach $5B by 2030, CAGR 12%."),
        "news": Evidence(source="web", url="https://finance.yahoo.com/x", title="N", snippet="story"),
        "reference": Evidence(source="arxiv", url="https://arxiv.org/abs/1", title="paper", snippet="study"),
        "discussion": Evidence(source="reddit", url="https://reddit.com/r/x", title="t", snippet="post"),
        "product": Evidence(source="web", url="https://habitshare.app/", title="HabitShare", snippet="app"),
        "fixture": Evidence(source="web", url="https://x", title="[fixture] X", snippet="placeholder"),
    }
    for expected, ev in cases.items():
        assert evidence_kind(ev) == expected, f"{expected} misclassified"


def test_only_substantive_kinds_are_extractable():
    barred = ["job", "market_report", "news", "fixture"]
    allowed = ["reference", "discussion", "product"]
    samples = {
        "job": Evidence(source="jobs", url="https://remotive.com/j", title="t", snippet="s"),
        "market_report": Evidence(source="web", url="https://x", title="t", snippet="CAGR forecast to 2031"),
        "news": Evidence(source="web", url="https://yahoo.com/x", title="t", snippet="s"),
        "fixture": Evidence(source="web", url="https://x", title="[fixture] t", snippet="s"),
        "reference": Evidence(source="wikipedia", url="https://wikipedia.org/x", title="t", snippet="s"),
        "discussion": Evidence(source="hackernews", url="https://news.ycombinator.com/x", title="t", snippet="s"),
        "product": Evidence(source="web", url="https://acme.io/", title="Acme", snippet="s"),
    }
    for k in barred:
        assert is_extractable(samples[k]) is False
    for k in allowed:
        assert is_extractable(samples[k]) is True


def _comp(ev: list[Evidence]) -> list[Competitor]:
    return cm.TOOL.run(evidence=[e.model_dump() for e in ev]).payload


# ── build_competitor_matrix ────────────────────────────────────────────────
def test_job_postings_are_not_competitors():
    ev = [Evidence(source="jobs", url="https://remotive.com/job/1",
                   title="Copywriter @ Coalition Technologies",
                   snippet="We offer remote work and support the team. Copywriter @ Coalition Technologies.")]
    names = [c.name.lower() for c in _comp(ev)]
    assert names == [] or all("coalition" not in n and "copywriter" not in n for n in names)


def test_market_report_and_job_hosts_excluded():
    ev = [
        Evidence(source="web", url="https://yahoo.com/finance/habit",
                 title="Habit market", snippet="Market size expected to reach $5B by 2030, CAGR 12%."),
        Evidence(source="web", url="https://wiseguyreports.com/r/1",
                 title="Report", snippet="This market research report offers forecast to 2031."),
        Evidence(source="web", url="https://remotive.com/remote-jobs/x",
                 title="Job", snippet="We offer a great role and support growth."),
    ]
    names = {c.name.lower() for c in _comp(ev)}
    assert not ({"yahoo", "wiseguyreports", "remotive"} & names)


def test_producthunt_title_is_surfaced_as_competitor():
    ev = [Evidence(source="producthunt", url="https://www.producthunt.com/posts/twinbit",
                   title="TwinBit", snippet="TwinBit lets couples share habits and sync streaks.")]
    names = {c.name for c in _comp(ev)}
    assert "TwinBit" in names  # real product surfaced despite producthunt.com being a research host


def test_show_hn_title_is_surfaced():
    ev = [Evidence(source="hackernews", url="https://news.ycombinator.com/item?id=1",
                   title="Show HN: HabitPair – shared habits for couples",
                   snippet="I built HabitPair so my partner and I can share habit streaks.")]
    names = {c.name for c in _comp(ev)}
    assert "HabitPair" in names


def test_real_product_domain_still_kept():
    ev = [Evidence(source="web", url="https://habitshare.app/",
                   title="HabitShare", snippet="HabitShare offers shared tracking. Free plan available.")]
    names = {c.name.lower() for c in _comp(ev)}
    assert any("habitshare" in n for n in names)


# ── extract_pain_points ────────────────────────────────────────────────────
def test_demand_evidence_yields_a_pain():
    ev = [Evidence(source="reddit", url="https://r/1", title="ask",
                   snippet="I was looking for a privacy-first habit tracker for couples but couldn't find one.")]
    pains = pp.TOOL.run(evidence=[e.model_dump() for e in ev]).payload
    assert len(pains) >= 1                    # unmet-need is a pain (was 0 before the demand tier)


def test_html_entities_are_decoded_in_pains():
    """A snippet with HTML entities ('I&#x27;m looking … couldn&#x27;t find') must decode to
    real text, not leak as junk like 'I& x27' after punctuation stripping."""
    ev = [Evidence(source="reddit", url="https://r/1", title="ask",
                   snippet="I&#x27;m looking for a privacy-first habit tracker but couldn&#x27;t find one.")]
    pains = pp.TOOL.run(evidence=[e.model_dump() for e in ev]).payload
    assert pains, "demand pain should still be extracted"
    joined = " ".join(p.text for p in pains).lower()
    assert "x27" not in joined and "&#" not in joined and "&amp;" not in joined


def test_nav_and_template_chrome_still_rejected():
    ev = [
        Evidence(source="web", url="https://x/1", title="nav", snippet="Log in Get Started Book a Demo"),
        Evidence(source="github", url="https://github.com/x/y/issues/1", title="t",
                 snippet="Steps to reproduce: open the app. Expected behavior: it works."),
    ]
    pains = pp.TOOL.run(evidence=[e.model_dump() for e in ev]).payload
    assert pains == []


# ── end-to-end cascade guard ───────────────────────────────────────────────
def test_job_text_never_becomes_a_feature():
    """The reported bug: a Remotive job posting flowed into the PRD as
    'Differentiator: copywriter @ coalition technologies'. With job evidence excluded from
    the competitor matrix, no such feature can be derived."""
    ev = [Evidence(source="jobs", url="https://remotive.com/job/1",
                   title="Copywriter @ Coalition Technologies",
                   snippet="We offer remote work and support the team.")]
    comps = _comp(ev)
    feats = pf.TOOL.run(pain_points=[], competitors=[c.model_dump() for c in comps]).payload
    titles = " ".join(f.title.lower() for f in feats)
    assert "copywriter" not in titles and "coalition" not in titles
