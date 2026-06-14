"""Pain noise filter — the contributor's exact polluted snippets must NOT become pains.

Closes finding (a): nav/CTA chrome, greetings, and issue-template scaffolding were ending up
as the PRD's headline 'Must' feature on noisy ideas (PR-review/security idea).
"""
from __future__ import annotations

from aps.state.models import Evidence
from aps.tools.analysis.extract_pain_points import TOOL, _pick_pain, _looks_like_noise


# the exact junk the contributor reported (each contains a cue further in, so it slipped through)
_NOISE = [
    "Log inGet StartedBook a Demo. Honestly the whole thing is broken.",
    "📚 Documentation Request Description I noticed that some features are missing here.",
    "Hi Claude autonomous plugin maintainer, I was looking but it doesn't work for me.",
]
_REAL = [
    "The resume parser is broken and keeps dropping valid PDFs.",
    "Candidate ranking is slow and confusing, I can't trust it.",
]


def test_noise_sentences_are_rejected():
    for snippet in _NOISE:
        # the leading chrome sentence is flagged; the whole item yields no clean pain
        ev = Evidence(source="web", url="https://x.com/a", title="", snippet=snippet)
        out = TOOL.run(evidence=[ev.model_dump()])
        for p in out.payload:
            # whatever (if anything) is extracted must NOT be the nav/greeting/template chrome
            low = p.text.lower()
            assert not low.startswith(("log in", "documentation request", "hi ", "📚"))
            assert "book a demo" not in low and "get started" not in low


def test_pure_chrome_yields_no_pain():
    ev = Evidence(source="web", url="https://x.com/a", title="Home",
                  snippet="Log in · Get Started · Book a Demo · View Pricing · Contact Sales")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_real_complaints_still_extracted():
    evs = [Evidence(source="reddit", url=f"https://reddit.com/{i}", title="rant", snippet=s)
           for i, s in enumerate(_REAL)]
    pains = TOOL.run(evidence=[e.model_dump() for e in evs]).payload
    assert len(pains) == 2
    assert any(p.severity.value == "high" for p in pains)
    assert all(not _looks_like_noise(p.text) for p in pains)


def test_complaint_after_chrome_extracts_the_complaint_not_chrome():
    # a real complaint sentence AFTER nav chrome → the complaint is what's kept
    snippet = ("Home Features Pricing Login. The export feature is completely broken and "
               "I waste hours every week.")
    ev = Evidence(source="web", url="https://acme.io/x", title="", snippet=snippet)
    pains = TOOL.run(evidence=[ev.model_dump()]).payload
    assert pains and "export" in pains[0].text.lower()
    assert "pricing" not in pains[0].text.lower()


def test_helper_classifies_examples():
    assert _looks_like_noise("Hi there, just wondering about this")
    assert _looks_like_noise("Documentation Request: add more")
    assert _looks_like_noise("Get Started Book a Demo today")
    assert not _looks_like_noise("the dashboard is painfully slow to load")
    assert _pick_pain("The app is broken and crashes constantly.")[1].value == "high"


def test_github_feature_request_title_does_not_block_snippet_pain():
    ev = Evidence(
        source="github",
        url="https://github.com/x/y/issues/42",
        title="Feature request: offline/privacy mode",
        snippet="I can't find a good privacy-first habit tracker that works offline.",
    )
    pains = TOOL.run(evidence=[ev.model_dump()]).payload
    assert pains, "pain in snippet must survive noisy GitHub title"
    assert any("privacy" in p.text.lower() or "find" in p.text.lower() for p in pains)


def test_demand_signal_cant_find_extracted_as_med():
    ev = Evidence(
        source="reddit",
        url="https://reddit.com/r/privacy/1",
        title="Looking for a privacy-respecting habit tracker",
        snippet="Can't find a single app that works offline and doesn't send data to the cloud.",
    )
    pains = TOOL.run(evidence=[ev.model_dump()]).payload
    assert pains, "demand-type pain must be extracted"
    assert pains[0].severity.value in ("med", "high")


# ── adversarial hardening: a URL fragment / space-separated nav bar carries a pain cue but
#    is not a complaint. (Both slipped through before — see the deep-hardening pass.) ──────
def test_bare_url_with_cue_word_is_not_a_pain():
    # the path "/broken-links-guide" carries the cue "broken" but it's a link, not prose
    ev = Evidence(source="web", url="https://x.com/a", title="",
                  snippet="https://example.com/broken-links-guide")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_space_separated_navbar_with_cue_is_not_a_pain():
    ev = Evidence(source="web", url="https://x.com/a", title="",
                  snippet="Home Products Pricing About Login broken")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_helper_rejects_url_and_navbar_keeps_short_real_pain():
    assert _looks_like_noise("https://example.com/broken-links-guide")
    assert _looks_like_noise("Home Products Pricing About Login broken")
    assert not _looks_like_noise("it is unusable")          # short, but genuine prose


# ── second live-data pass: forum solicitations, marketing/article titles, positive idioms,
#    and "born out of" pitches still leaked on the subscription-tracker run. ─────────────────
def test_opinion_solicitation_question_is_not_a_pain():
    assert _looks_like_noise("What are your thoughts or pain points on subscription charges?")
    assert _looks_like_noise("Anyone else frustrated with this, or am I the only one?")
    # but a rhetorical COMPLAINT question is still a pain
    assert not _looks_like_noise("Why do companies make it so hard to cancel subscriptions?")


def test_marketing_and_title_case_headlines_are_not_pains():
    assert _looks_like_noise("Why You Need a Subscription Tracker App")
    assert _looks_like_noise("The 7 Best Subscription Management Apps in 2026")
    assert _looks_like_noise("When Websites Make It Hard to Cancel")
    # a lowercase complaint that names a couple of products is NOT a headline
    assert not _looks_like_noise("the Slack and Notion integration is broken and loses data")


def test_positive_idiom_is_not_a_pain():
    assert _looks_like_noise("Currently in pre-release and honestly can't believe this worked")
    assert _looks_like_noise("This works great and I highly recommend it")


def test_born_out_pitch_and_marketing_effort_are_not_pains():
    assert _looks_like_noise("SpeechPro was born out of my frustration during university")
    assert _looks_like_noise("The market, we work hard to share a wide range of offers")


# ── live-data hardening: real GitHub/HN/web snippets that leaked garbage pains before. Each
#    cascaded into junk feature titles, persona goals, and TRD entities. (Found during live testing.)
def test_product_pitch_is_not_a_pain():
    # a Show-HN founder pitch ("we built this because…") is not a user complaint
    ev = Evidence(source="hackernews", url="https://h/1", title="Show HN: our hiring tool",
                  snippet="Couple friends and I built this cause we hated the direction hiring is going.")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_repo_description_with_star_prefix_is_not_a_pain():
    ev = Evidence(source="github", url="https://g/1", title="org/FairHiringProtocol",
                  snippet="4★ The Fair Hiring Protocol (FHP) is an open, community standard designed to fix hiring.")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_listing_metadata_is_not_a_pain():
    ev = Evidence(source="hackernews", url="https://h/2",
                  title="Looking for Employers for the job fair", snippet="1 points, 0 comments")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_vcs_missing_file_gripe_is_not_a_pain():
    # the dot-split used to fragment "resume.txt" so the VCS filter missed it; now it doesn't
    ev = Evidence(source="github", url="https://g/2", title="Missing resume.txt",
                  snippet="Where can we find resume.txt? It does not exist into the repo.")
    assert TOOL.run(evidence=[ev.model_dump()]).payload == []


def test_real_market_pain_survives_and_is_not_truncated():
    # a genuine multi-clause complaint stays a complete thought (no dangling "… and")
    ev = Evidence(source="web", url="https://x/1", title="AI recruiting review",
                  snippet="Sourcing is slower, candidate competition is fiercer, and the old "
                          "keyword playbook is failing recruiters everywhere.")
    pains = TOOL.run(evidence=[ev.model_dump()]).payload
    assert pains and not pains[0].text.rstrip().endswith((" and", " the", " is", ","))


def test_plain_snippet_demand_pain_no_title_noise():
    ev = Evidence(
        source="reddit",
        url="https://reddit.com/r/privacy/2",
        title="",
        snippet="Can't find a privacy-respecting habit tracker. Would love an offline-first option.",
    )
    pains = TOOL.run(evidence=[ev.model_dump()]).payload
    assert pains, "bare demand snippet must yield at least one pain"


def test_product_description_is_not_a_pain():
    # Phase 4a: a repo/product blurb (generic "X is a <…> tool/app/platform/…") masquerading as a
    # pain is rejected — it describes a product, it doesn't voice a user frustration.
    for blurb in [
        "ZeroTrace is a powerful ethical hacking tool for anonymization via Tor.",
        "ActivityWatch is an open-source automated time-tracking app.",
        "Foo is a fast self-hosted analytics platform for teams.",
    ]:
        assert _looks_like_noise(blurb), f"blurb slipped through: {blurb!r}"


def test_product_description_with_real_complaint_survives():
    # …but a product mention FOLLOWED by an actual complaint is still a pain.
    for s in [
        "ActivityWatch is a free time-tracking app but it is broken and crashes constantly.",
        "Toggl is a popular tracking tool, however it can't export and the sync is slow.",
    ]:
        assert not _looks_like_noise(s), f"real complaint wrongly dropped: {s!r}"
    ev = Evidence(source="hackernews", url="https://h/1", title="",
                  snippet="ActivityWatch is a free time-tracking app but it is broken and crashes constantly.")
    assert TOOL.run(evidence=[ev.model_dump()]).payload, "complaint after a product mention must yield a pain"
