"""Provider/key resolution + honest degradation reasons.

Covers the fix for the silent-401 bug: empty keys count as unset, the NIM factory raises
instead of sending a placeholder, the provider auto-detects from the available key, a
provider/key mismatch is a loud message, and every degraded brief records WHY.
"""
from __future__ import annotations

import pytest

from aps.config.settings import (
    nvidia_key, resolved_provider, get_chat_model, describe_runtime,
)
from aps.infra.llm import has_llm_key, key_mismatch
from aps.agents.research.stub import stub_research
from aps.state.models import ResearchReturn

_KEYS = ("NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "APS_MODEL_PROVIDER")


@pytest.fixture
def clean_env(monkeypatch):
    for k in _KEYS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_empty_or_whitespace_key_counts_as_unset(clean_env):
    clean_env.setenv("NVIDIA_API_KEY", "   ")
    assert nvidia_key() == ""          # whitespace stripped to empty
    clean_env.setenv("NVIDIA_API_KEY", "nvapi-real")
    assert nvidia_key() == "nvapi-real"


def test_resolved_provider_autodetects_from_single_key(clean_env):
    clean_env.setenv("NVIDIA_API_KEY", "nvapi-x")
    assert resolved_provider() == "nim"          # NVIDIA-only env → nim, no switch needed
    clean_env.delenv("NVIDIA_API_KEY")
    clean_env.setenv("GEMINI_API_KEY", "g-x")
    assert resolved_provider() == "gemini"


def test_explicit_provider_always_wins(clean_env):
    clean_env.setenv("APS_MODEL_PROVIDER", "gemini")
    clean_env.setenv("NVIDIA_API_KEY", "nvapi-x")   # only NVIDIA key present
    assert resolved_provider() == "gemini"          # but explicit setting wins (a real misconfig)
    assert key_mismatch() is not None               # ...and is surfaced loudly
    assert "NVIDIA key IS set" in key_mismatch()


def test_nim_factory_raises_without_key_no_placeholder(clean_env):
    clean_env.setenv("APS_MODEL_PROVIDER", "nim")
    # no NVIDIA_API_KEY → must raise, never construct a client with a bogus "placeholder"
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        get_chat_model()


def test_has_llm_key_respects_empty(clean_env):
    clean_env.setenv("APS_MODEL_PROVIDER", "nim")
    clean_env.setenv("NVIDIA_API_KEY", "")
    assert has_llm_key() is False
    clean_env.setenv("NVIDIA_API_KEY", "nvapi-real")
    assert has_llm_key() is True


def test_key_mismatch_specific_remedy(clean_env):
    clean_env.setenv("APS_MODEL_PROVIDER", "nim")
    clean_env.setenv("GEMINI_API_KEY", "g-x")        # only a Gemini key, but provider=nim
    msg = key_mismatch()
    assert msg and "NVIDIA_API_KEY" in msg and "APS_MODEL_PROVIDER=gemini" in msg


def test_describe_runtime_never_leaks_key(clean_env):
    clean_env.setenv("APS_MODEL_PROVIDER", "nim")
    clean_env.setenv("NVIDIA_API_KEY", "nvapi-secret")
    rt = describe_runtime()
    assert "provider=nim" in rt and "key=present" in rt
    assert "nvapi-secret" not in rt                  # presence only, never the value


def test_stub_research_records_reason():
    r = stub_research("a habit tracker", reason="no_llm_key")
    assert r.degraded is True
    assert r.degrade_reason == "no_llm_key"
    assert "no_llm_key" in r.evidence[0].snippet     # self-diagnosing artifact


def test_degrade_reason_roundtrips_through_json():
    r = ResearchReturn(idea="x", degraded=True, degrade_reason="llm_auth_401")
    again = ResearchReturn.model_validate_json(r.model_dump_json())
    assert again.degrade_reason == "llm_auth_401"
