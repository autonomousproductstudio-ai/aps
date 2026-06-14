"""Phase 3 — the language-level relevance judge (research/_relevance.judge).

The deterministic lexical gate can't disambiguate word senses (a particle-physics "tracker" paper
shares the word with an activity-tracker app). The LLM judge is the second pass that discards such
false-positives and rescues borderline true-positives. It is gated hard (enabled + key + not-pytest),
so under pytest it must be a NO-OP — these tests pin that, plus the keep/discard behavior with the
model call monkeypatched.
"""
from __future__ import annotations

from types import SimpleNamespace

from aps.agents.research import _relevance as rel
from aps.state.models import Evidence


def _ev(title, score):
    e = Evidence(source="web", url=f"https://x/{title}", title=title, snippet=title + " details")
    e.relevance = score
    return e


def test_judge_is_noop_under_pytest_even_when_enabled():
    # enabled flag on, but "pytest" in sys.modules ⇒ deterministic set returned unchanged (hermetic)
    s = SimpleNamespace(enable_relevance_llm=True)
    det = [_ev("on-topic", 0.6)]
    assert rel.judge("idea", det, det, s, min_score=0.15) is det


def test_judge_disabled_returns_deterministic_set():
    s = SimpleNamespace(enable_relevance_llm=False)
    det = [_ev("a", 0.5), _ev("b", 0.4)]
    assert rel.judge("idea", det, det, s, min_score=0.15) == det


def test_judge_discards_and_rescues_when_active(monkeypatch):
    # force the gate open and stub the model so no network/key is needed
    monkeypatch.setattr(rel, "_enabled", lambda settings: True)

    on = _ev("Activity tracker privacy leak", 0.6)        # det-relevant, truly on-topic
    false_pos = _ev("CMS Strip Tracker physics paper", 0.4)  # det-relevant but off-topic (word sense)
    borderline = _ev("self-hosted activity logger", 0.10)    # below cutoff → candidate for rescue
    det_relevant = [on, false_pos]
    all_ev = [on, false_pos, borderline]

    # the model keeps #1 (on) and #3 (borderline rescue), drops #2 (physics false-positive)
    class _Resp:
        content = "1, 3"

    # judge imports these lazily from their home modules — patch there, not on `rel`
    import aps.config.settings as settings
    import aps.infra.llm as llm
    monkeypatch.setattr(settings, "get_chat_model",
                        lambda **k: SimpleNamespace(invoke=lambda msgs: _Resp()), raising=False)
    monkeypatch.setattr(llm, "acquire_llm", lambda *a, **k: None, raising=False)

    out = rel.judge("Private Activity Tracker", all_ev, det_relevant, SimpleNamespace(), min_score=0.15)
    titles = {e.title for e in out}
    assert "Activity tracker privacy leak" in titles          # kept
    assert "self-hosted activity logger" in titles            # rescued from borderline
    assert "CMS Strip Tracker physics paper" not in titles    # discarded false-positive


def test_judge_empty_verdict_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setattr(rel, "_enabled", lambda settings: True)
    det = [_ev("on-topic", 0.6)]

    class _Resp:
        content = "none"

    import aps.config.settings as settings
    import aps.infra.llm as llm
    monkeypatch.setattr(settings, "get_chat_model",
                        lambda **k: SimpleNamespace(invoke=lambda m: _Resp()), raising=False)
    monkeypatch.setattr(llm, "acquire_llm", lambda *a, **k: None, raising=False)
    # a 'none'/garbage verdict must NOT zero out the brief — fall back to the deterministic set
    assert rel.judge("idea", det, det, SimpleNamespace(), min_score=0.15) == det
