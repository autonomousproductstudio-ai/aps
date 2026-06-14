"""FailoverChatModel (multipleAPIplan P2) — try → next on retryable errors, offline + mocked."""
from __future__ import annotations

import pytest

from aps.config.failover import FailoverChatModel, _is_retryable, build_failover_model


# ── fake provider runtimes ────────────────────────────────────────────────────
class _FakeModel:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.bound = None

    def bind_tools(self, tools, **kwargs):
        self.bound = tools
        return self

    def invoke(self, messages, **kwargs):
        if self._raises is not None:
            raise self._raises
        return self._result


class _FakeRuntime:
    def __init__(self, name, model):
        self.name = name
        self._model = model

    def chat_model(self):
        return self._model


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    # keep tests instant + deterministic (don't exercise the real rate limiter here)
    import aps.infra.llm as llm
    monkeypatch.setattr(llm, "acquire_llm", lambda *a, **k: 0.0)
    # reset the global circuit breaker so chain order isn't reordered by prior tests' trips
    from aps.config import quota
    quota.BREAKER.reset()
    yield
    quota.BREAKER.reset()


def _fail(msg):
    return RuntimeError(msg)


# ── retryability classification ───────────────────────────────────────────────
def test_is_retryable_classifies():
    assert _is_retryable(_fail("HTTP 429 rate limit exceeded"))
    assert _is_retryable(_fail("503 Service Unavailable"))
    assert _is_retryable(_fail("Connection timed out"))
    assert _is_retryable(_fail("401 Unauthorized"))
    assert _is_retryable(ImportError("no langchain_anthropic"))
    assert not _is_retryable(ValueError("malformed tool schema"))   # real bug → don't mask


# ── failover behavior ─────────────────────────────────────────────────────────
def test_fails_over_to_next_on_retryable():
    a = _FakeRuntime("groq", _FakeModel(raises=_fail("429 rate limit")))
    b = _FakeRuntime("gemini", _FakeModel(result="OK"))
    m = FailoverChatModel([a, b])
    assert m.invoke(["hi"]) == "OK"
    assert m.last_provider == "gemini"


def test_non_retryable_raises_immediately_no_failover():
    a = _FakeRuntime("groq", _FakeModel(raises=ValueError("bad prompt")))
    b = _FakeRuntime("gemini", _FakeModel(result="OK"))
    m = FailoverChatModel([a, b])
    with pytest.raises(ValueError):
        m.invoke(["hi"])
    assert m.last_provider is None        # never reached provider b


def test_all_retryable_fail_raises_last():
    a = _FakeRuntime("groq", _FakeModel(raises=_fail("429")))
    b = _FakeRuntime("gemini", _FakeModel(raises=_fail("503")))
    m = FailoverChatModel([a, b])
    with pytest.raises(RuntimeError, match="503"):
        m.invoke(["hi"])


def test_bind_tools_propagates_to_the_chosen_provider():
    a = _FakeRuntime("groq", _FakeModel(raises=_fail("timeout")))
    okmodel = _FakeModel(result="OK")
    b = _FakeRuntime("gemini", okmodel)
    m = FailoverChatModel([a, b]).bind_tools(["TOOL_A", "TOOL_B"])
    assert m.invoke(["hi"]) == "OK"
    assert okmodel.bound == ["TOOL_A", "TOOL_B"]    # tools bound on the provider that answered


def test_providers_property():
    m = FailoverChatModel([_FakeRuntime("groq", _FakeModel()), _FakeRuntime("nim", _FakeModel())])
    assert m.providers == ["groq", "nim"]


# ── build_failover_model + wiring ─────────────────────────────────────────────
def test_build_failover_model_from_chain(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,gemini")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    m = build_failover_model(0.2)
    assert isinstance(m, FailoverChatModel)
    assert m.providers == ["groq", "gemini"]        # built lazily — no network


def test_build_failover_model_empty_chain_raises(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq")   # no key → not available
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No LLM provider"):
        build_failover_model()


def test_get_chat_model_returns_failover_when_chain_set(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    from aps.config.settings import get_chat_model
    assert isinstance(get_chat_model(), FailoverChatModel)


def test_has_llm_key_uses_chain_when_set(monkeypatch):
    from aps.infra.llm import has_llm_key
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,cerebras")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    assert has_llm_key() is False
    monkeypatch.setenv("CEREBRAS_API_KEY", "k")
    assert has_llm_key() is True


def test_ui_pin_routes_through_failover_not_a_hard_lock(monkeypatch):
    """A per-run/UI provider pin becomes the PREFERRED chain head but STILL fails over — it must
    not return a single-provider model that dies when that provider is exhausted (the demo bug)."""
    from aps.config import settings
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "openai,nim,gemini")
    for k in ("OPENAI_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(k, "k")
    settings.get_settings.cache_clear()
    tok = settings.set_run_model("gemini", "gemini-2.5-flash")   # user picks the exhausted provider
    try:
        m = settings.get_chat_model()
        assert isinstance(m, FailoverChatModel)                   # failover, NOT a single gemini model
        order = [rt.name for rt in m._runtimes]
        assert order[0] == "gemini"                               # pin honored as the PREFERRED head
        assert set(order) == {"openai", "nim", "gemini"}          # …but the rest stay as failover
    finally:
        settings.reset_run_model(tok)
        settings.get_settings.cache_clear()
