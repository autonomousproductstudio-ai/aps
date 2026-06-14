"""End-to-end: the contributor's noisy idea yields a CLEAN PRD (compression → PRD).

Feeds the exact noise classes that polluted the PR-review/security run (nav chrome, emoji
issue-templates, greetings, directory/social domains) through the real compression + Product
agent, and asserts the resulting PRD features / competitors are credible — no nav text as the
headline feature, no LinkedIn-as-competitor.
"""
from __future__ import annotations

from aps.state.models import Evidence
from aps.agents.research.agent import _compress
from aps.agents.product.agent import run_product

IDEA = "AI tool that reviews PRs for security vulnerabilities"

NOISY_EVIDENCE = [
    Evidence(source="web", url="https://greptile.io/", title="Greptile",
             snippet="Log inGet StartedBook a Demo. The current manual code review is broken and slow."),
    Evidence(source="github", url="https://github.com/x/y/issues/1", title="issue",
             snippet="\U0001F4DA Documentation Request Description I noticed that scanning is missing."),
    Evidence(source="web", url="https://www.linkedin.com/posts/someone", title="post",
             snippet="Hi everyone! Sharing thoughts — supports lots of integrations and a dashboard."),
    Evidence(source="web", url="https://crozdesk.com/security", title="directory",
             snippet="Compare the best code review tools. Offers analytics and reporting."),
    Evidence(source="web", url="https://zeropath.com/pricing", title="Zeropath",
             snippet="Zeropath offers SAST scanning and integrates with GitHub. Pricing $40/mo."),
    Evidence(source="reddit", url="https://reddit.com/r/x/2", title="rant",
             snippet="Manual PR security review is painful and we waste hours every single sprint."),
]


def test_noisy_evidence_produces_clean_prd():
    research = _compress(IDEA, NOISY_EVIDENCE)
    prd = run_product(research)

    # competitors: real product kept; social / directory dropped
    comp_names = {c.name.lower() for c in research.competitors}
    assert any("zeropath" in n for n in comp_names), comp_names
    assert "linkedin" not in comp_names and "crozdesk" not in comp_names

    # pains are real complaints, not page chrome
    for p in research.pain_points:
        low = p.text.lower()
        assert not low.startswith(("log in", "documentation request", "hi "))
        assert "book a demo" not in low

    # PRD features (derived from pains) are credible — never nav/greeting/template chrome
    titles = [f.title.lower() for f in prd.features]
    assert titles, "PRD should still produce features"
    for t in titles:
        assert "book a demo" not in t and "get started" not in t
        assert "documentation request" not in t
        assert not t.startswith("solve: hi ")
    # the genuine complaint made it through to a feature
    assert any("review" in t or "scan" in t or "security" in t or "manual" in t for t in titles)


def test_off_topic_complaint_does_not_become_a_pain():
    # An on-topic complaint + an off-topic-but-valid complaint (shares no idea vocabulary).
    # The relevance gate must keep the on-topic pain and reject the off-topic one — even though
    # both are syntactically real complaints the noise filter alone would pass.
    evidence = [
        Evidence(source="reddit", url="https://reddit.com/r/x/1",
                 title="rant", snippet="Manual PR security review is painful and slow every sprint."),
        Evidence(source="reddit", url="https://reddit.com/r/x/2",
                 title="rant", snippet="My espresso machine is broken and the milk frother keeps clogging."),
    ]
    research = _compress(IDEA, evidence)
    pains = " ".join(p.text.lower() for p in research.pain_points)
    assert "espresso" not in pains and "frother" not in pains   # off-topic complaint gated out
    assert research.pain_points, "the on-topic security-review complaint should survive"
    assert "review" in pains or "security" in pains or "manual" in pains
