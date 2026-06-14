"""Adversarial hardening for user-story phrasing and tech-stack cue matching.

- User stories must name a clean CAPABILITY ("I want bulk delete"), not quote a raw pain
  ("I want to overcome 'no way to bulk delete'").
- Tech-stack cues must match at word boundaries, not as substrings — "blockchain"/"email"/"html"
  must NOT trigger ML serving (the 'ai' in blockch-ai-n / the 'ml' in ht-ml).
"""
from __future__ import annotations

from aps.state.models import Persona, PainPoint, Severity
from aps.tools.product.generate_user_stories import TOOL as STORIES
from aps.tools.architecture.choose_tech_stack import TOOL as STACK


def _stories(pains):
    p = [Persona(name="Recruiter", role="hiring manager", goals=["hire fast"]).model_dump()]
    pp = [PainPoint(text=t, severity=Severity.HIGH).model_dump() for t in pains]
    return STORIES.run(personas=p, pain_points=pp).payload


def test_user_story_names_capability_not_raw_pain():
    out = _stories(["no way to bulk delete", "Candidate ranking is slow"])
    assert all(s.lower().startswith("as a") for s in out)
    assert any("i want bulk delete" in s.lower() for s in out)
    assert any("i want candidate ranking" in s.lower() for s in out)
    # the clumsy "overcome '<raw pain>'" phrasing is gone
    assert not any("overcome '" in s for s in out)


def test_user_stories_dedupe_shared_capability():
    # two pains that map to the same capability theme → one story, not two identical ones
    out = _stories(["It is unusable", "Reliability & stability"])
    assert len(out) == 1


def test_user_stories_handle_empty_pains():
    p = [Persona(name="U", role="user").model_dump()]
    out = STORIES.run(personas=p, pain_points=[]).payload
    assert out and out[0].lower().startswith("as a")


def _stack_adds(reqs, scale=""):
    rows = STACK.run(requirements=reqs, scale_estimate=scale).payload
    return [r.split(":")[0] for r in rows[4:]]   # drop the 4 baseline rows


def test_substring_cues_do_not_false_trigger_ml():
    # 'ai' inside blockchain / email / training, 'ml' inside html → NOT ML serving
    assert "ML serving" not in _stack_adds(["blockchain ledger"], "10k users")
    assert "ML serving" not in _stack_adds(["user training portal"])
    assert "ML serving" not in _stack_adds(["html email templates"])


def test_real_cues_still_add_components():
    adds = _stack_adds(["AI scoring of resumes", "search and match candidates"], "high scale")
    assert "ML serving" in adds and "Search" in adds
    assert "Realtime" in _stack_adds(["live streaming dashboard"])
    # prefix/stem matching preserved: 'notif' → 'notifications'
    assert "Realtime" in _stack_adds(["email notifications"])


def test_baseline_always_present():
    rows = STACK.run(requirements=[], scale_estimate="").payload
    assert len(rows) == 4 and rows[0].startswith("Backend")
