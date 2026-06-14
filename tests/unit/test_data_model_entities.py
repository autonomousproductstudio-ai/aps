"""Adversarial hardening: the data model must mint DOMAIN-NOUN entities, never adjectives,
adverbs, or pure-verb gerunds.

Before this, ideas like "a privacy-first PERSONAL finance tracker", "REALTIME MULTIPLAYER chess",
or "platform for MANAGING social media posts" produced database entities named `Personal`,
`Realtime`, `Multiplayer`, `Managing`, `Decentralized`, `Quickly`, `Damn` — which then become
OpenAPI schemas and API paths. These pin the denylist + morphological (-ly / -ized) guards.
"""
from __future__ import annotations

from aps.tools.architecture.design_data_model import TOOL, _candidate_nouns


def _entities(idea: str) -> set[str]:
    return set(TOOL.run(idea=idea).payload["entities"].keys())


# adjectives / adverbs / pure gerunds that previously leaked, mapped to the head noun that should win
_LEAK_CASES = [
    ("a privacy-first personal finance tracker for couples", {"Personal"}, {"Finance", "Tracker"}),
    ("realtime multiplayer chess with ELO ranking", {"Realtime", "Multiplayer"}, {"Chess", "Ranking"}),
    ("the best damn app to quickly delete annoying spam emails", {"Damn", "Quickly"}, {"Email"}),
    ("platform for managing scheduled social media posts", {"Managing", "Social"}, {"Media", "Post"}),
    ("blockchain-based decentralized voting system", {"Decentralized"}, {"Voting", "System"}),
    ("app for optimizing personalized workout plans", {"Optimizing", "Personalized"}, {"Workout", "Plan"}),
]


def test_modifiers_never_become_entities_but_head_nouns_do():
    for idea, forbidden, expected in _LEAK_CASES:
        ents = _entities(idea)
        assert not (ents & forbidden), f"{idea!r} leaked {ents & forbidden}"
        assert expected <= ents, f"{idea!r} lost head nouns {expected - ents}"


def test_nominal_ing_and_ly_nouns_are_preserved():
    # -ing words that are genuine entities (not pure-verb gerunds) survive
    assert {"Planning", "Screening", "Ranking"} <= _entities(
        "resume screening with candidate ranking and sprint planning")
    # -ly words that are real nouns survive the adverb rule
    ents = _entities("family meal supply tracker")
    assert "Family" in ents and "Supply" in ents


def test_candidate_nouns_drops_adverbs_and_participles():
    toks = _candidate_nouns("quickly decentralized personalized optimizing finance tracker")
    assert "quickly" not in toks and "decentralized" not in toks
    assert "personalized" not in toks and "optimizing" not in toks
    assert "finance" in toks and "tracker" in toks


def test_user_entity_always_present_and_model_non_trivial():
    ents = _entities("app")            # degenerate idea → still a usable model
    assert "User" in ents and len(ents) >= 2


def test_continuation_conjunctions_never_become_entities():
    # the /howevers bug: a fragment leading with "However/Therefore/Meanwhile" must not mint an
    # entity (which would become a /howevers OpenAPI path). Head nouns still survive.
    from aps.state.models import Feature
    for lead in ("However", "Therefore", "Meanwhile", "Moreover", "Furthermore"):
        ents = {e.lower() for e in TOOL.run(
            idea=f"{lead} the activity tracker leaks user data",
            features=[Feature(title=f"{lead} about a week the sync failed",
                              description="x", priority="Should").model_dump()],
        ).payload["entities"]}
        assert lead.lower() not in ents, f"{lead!r} leaked as an entity: {ents}"
        assert "tracker" in ents or "activity" in ents
