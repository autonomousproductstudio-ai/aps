"""Per-provider LLM rate limiting (multipleAPIplan P3) — each provider its own RPM bucket."""
from __future__ import annotations

import pytest

import aps.infra.llm as llm


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # fresh limiter + configured-set per test so env overrides take effect deterministically
    monkeypatch.setattr(llm, "_LIMITER", None)
    monkeypatch.setattr(llm, "_CONFIGURED", set())
    for v in ("APS_GROQ_RPM", "APS_GEMINI_RPM"):
        monkeypatch.delenv(v, raising=False)


def test_provider_rpm_from_registry():
    assert llm._provider_rpm("groq") == 30
    assert llm._provider_rpm("gemini") == 15
    assert llm._provider_rpm("nim") == 40
    assert llm._provider_rpm("llm") is None          # generic source → default bucket
    assert llm._provider_rpm("bogus") is None


def test_provider_rpm_env_override(monkeypatch):
    monkeypatch.setenv("APS_GROQ_RPM", "7")
    assert llm._provider_rpm("groq") == 7


def test_acquire_configures_provider_bucket_once():
    assert llm.acquire_llm("groq") == 0.0            # first token free, no error
    # the provider's bucket now exists, sized to its rpm (30), separate from "gemini"
    assert "groq" in llm._CONFIGURED
    lim = llm._limiter()
    assert lim._buckets["groq"].capacity == 30.0


def test_providers_have_isolated_buckets():
    # draining one provider's bucket does not throttle another (different keys)
    for _ in range(5):
        assert llm.acquire_llm("groq", ) >= 0.0
    assert llm.acquire_llm("gemini") == 0.0          # untouched bucket → free
