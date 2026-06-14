"""Research relevance gate — score evidence against the idea and keep pains on-topic.

The defect this guards: an off-topic-but-syntactically-valid complaint ("YouTube AdBlock is
missing" for a "Private Activity Tracker") passes the noise filter and seeds a bogus pain/feature.
The deterministic lexical scorer + the `_compress` pain gate must drop it, while keeping genuinely
on-topic evidence — and never silently emitting zero pains.
"""
from __future__ import annotations

from aps.tools.analysis.score_evidence_relevance import idea_profile, relevance_score, TOOL
from aps.agents.research.agent import _compress
from aps.config.settings import get_settings
from aps.state.models import Evidence

IDEA = "Private Activity Tracker"


def _ev(title, snippet, source="web", url="https://x/1"):
    return Evidence(source=source, url=url, title=title, snippet=snippet)


def test_on_topic_scores_high_off_topic_scores_zero():
    prof = idea_profile(IDEA)
    on = _ev("Activity trackers", "this activity tracker leaks location data to advertisers")
    off = _ev("YouTube AdBlock", "the adblock popup is missing in the new youtube ui")
    assert relevance_score(prof, on) >= 0.3
    assert relevance_score(prof, off) == 0.0


def test_morphology_match_catches_inflections():
    # private~privacy, tracker~tracking — a singular-stem intersection would miss these
    prof = idea_profile(IDEA)
    morph = _ev("Privacy-first tracking", "a private activity tracking app that respects users")
    assert relevance_score(prof, morph) >= 0.5


def test_off_domain_junk_is_rejected():
    # off-domain spam that shares one incidental word is hard-rejected by the junk lexicon
    prof = idea_profile(IDEA)
    assert relevance_score(prof, _ev("Stake bonus", "Stake bonus cannot be reached")) == 0.0
    assert relevance_score(prof, _ev("Sales role", "High-ticket financial sales specialist hiring now")) == 0.0


def test_degenerate_idea_does_not_gate_everything():
    # an all-stopword idea has no profile → never zero out evidence (returns 1.0)
    prof = idea_profile("the a an of to")
    assert prof == set()
    assert relevance_score(prof, _ev("x", "anything at all")) == 1.0


def test_tool_tags_and_optionally_filters():
    rows = [_ev("Activity trackers", "activity tracker privacy leak"),
            _ev("YouTube AdBlock", "adblock popup missing youtube")]
    out = TOOL.run(idea=IDEA, evidence=[r.model_dump() for r in rows], min_score=0.15).evidence
    # min_score drops the off-topic item; the kept one carries a populated relevance score
    assert len(out) == 1 and out[0].title == "Activity trackers"
    assert out[0].relevance and out[0].relevance > 0.15


def test_compress_gates_off_topic_pain_but_keeps_on_topic():
    s = get_settings()
    assert s.enable_relevance_gate  # default on
    evidence = [
        _ev("Activity tracker rant", "the activity tracker is slow and keeps crashing on every sync",
            source="reddit", url="https://r/1"),
        _ev("YouTube AdBlock", "youtube adblock is broken and missing in the new ui",
            source="github", url="https://g/1"),
    ]
    res = _compress(IDEA, evidence)
    pain_text = " ".join(p.text.lower() for p in res.pain_points)
    assert "youtube" not in pain_text and "adblock" not in pain_text   # off-topic pain gated out
    assert res.pain_points, "the on-topic complaint should still yield a pain"
    assert 0.0 <= res.evidence_relevance <= 1.0
    # every evidence item got scored
    assert all(e.relevance is not None for e in res.evidence)


def test_compress_degrades_when_nothing_relevant():
    # all evidence off-topic for the idea → floor guard keeps top-K but marks the brief degraded
    evidence = [
        _ev("YouTube AdBlock", "youtube adblock popup is missing", source="github", url="https://g/2"),
        _ev("Gmail addon", "the gmail addon keeps crashing on send", source="web", url="https://w/2"),
    ]
    res = _compress(IDEA, evidence)
    assert res.degraded is True and res.degrade_reason == "low_relevance"


def test_flag_off_disables_gate(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APS_ENABLE_RELEVANCE_GATE", "false")
    try:
        evidence = [_ev("YouTube AdBlock", "youtube adblock is broken and missing",
                        source="github", url="https://g/3")]
        res = _compress(IDEA, evidence)
        # gate off ⇒ the off-topic complaint is NOT filtered; relevance stays unscored
        assert res.degraded is False
        assert all(e.relevance is None for e in res.evidence)
    finally:
        get_settings.cache_clear()
