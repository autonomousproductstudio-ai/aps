"""Intent-based query planning — idea-anchored search phrases + sharp fan-out sub-questions.

Under pytest there's no LLM key, so `plan_queries`/`plan_subtopics` exercise their DETERMINISTIC
fallbacks — which is exactly what must carry the "ask on-topic questions" behavior. These tests
pin the fallback paths (idea-anchored, deduped, deterministic) and the keyless wiring.
"""
from __future__ import annotations

from aps.agents.research import supervisor as sup
from aps.agents.research import keyless as kl
from aps.config.settings import get_settings

IDEA = "Private Activity Tracker"


def test_plan_queries_fallback_is_idea_anchored_and_deduped():
    qs = sup.plan_queries(IDEA)
    assert len(qs) >= 5
    assert len(qs) == len({q.lower() for q in qs})          # deduped
    assert all("activity" in q.lower() or "tracker" in q.lower() for q in qs)  # anchored to idea
    assert qs == sup.plan_queries(IDEA)                     # deterministic


def test_plan_queries_respects_count():
    assert len(sup.plan_queries(IDEA, n=3)) <= 3


def test_fallback_subtopics_name_the_idea_not_a_bare_category():
    subs = sup._fallback_subtopics(IDEA, 3)
    assert len(subs) == 3
    # every sub-question names the idea (sharp), not the old generic category labels
    assert all("activity tracker" in s.lower() for s in subs)
    assert subs != sup._GENERIC_SUBTOPICS[:3]
    assert "user pain points & complaints with existing solutions" not in subs


def test_flag_off_restores_generic_subtopics(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APS_ENABLE_QUERY_PLANNING", "false")
    try:
        assert sup._fallback_subtopics(IDEA, 3) == sup._GENERIC_SUBTOPICS[:3]
    finally:
        get_settings.cache_clear()


def test_plan_subtopics_uses_idea_anchored_fallback_without_key():
    # no key under pytest → plan_subtopics returns the idea-anchored fallback
    subs = sup.plan_subtopics(IDEA, k=3)
    assert subs and all("activity tracker" in s.lower() for s in subs)


def test_keyless_issues_planned_phrases_across_tools(monkeypatch):
    # capture the query= each no-key tool is asked; assert it's the idea-anchored phrase set,
    # not a single raw-idea query.
    get_settings.cache_clear()
    seen_queries: list[str] = []

    class _Res:
        ok = True
        evidence: list = []

    class _Tool:
        def run(self, *, query, **extra):
            seen_queries.append(query)
            return _Res()

    import importlib
    monkeypatch.setattr(importlib, "import_module", lambda _p: type("M", (), {"TOOL": _Tool()}))
    monkeypatch.setattr(kl, "_compress", lambda idea, ev: ("compressed", idea, ev)[0])

    kl.keyless_research(IDEA)
    try:
        assert len(set(seen_queries)) >= 2                  # multiple distinct planned phrases
        assert any("activity" in q.lower() or "tracker" in q.lower() for q in seen_queries)
        assert seen_queries != [IDEA]                       # not just the bare idea
    finally:
        get_settings.cache_clear()


def test_keyless_flag_off_uses_single_token_query(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APS_ENABLE_QUERY_PLANNING", "false")
    try:
        qs = kl._keyless_queries(IDEA)
        assert len(qs) == 1 and "activity" in qs[0].lower()  # the prior single token-query path
    finally:
        get_settings.cache_clear()


def test_gather_evidence_accepts_seed_queries():
    # signature/contract check: seed_queries is an accepted keyword (the single-unit path passes it)
    import inspect
    from aps.agents.research.agent import gather_evidence
    assert "seed_queries" in inspect.signature(gather_evidence).parameters
