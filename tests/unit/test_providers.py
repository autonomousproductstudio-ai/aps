"""Multi-provider registry + chain resolution (multipleAPIplan P1) — offline, deterministic."""
from __future__ import annotations

import pytest

from aps.config.providers import REGISTRY, DEFAULT_CHAIN, provider_keys, provider_available, \
    resolved_provider_chain

# env vars the tests touch — cleared before each test so the host env can't leak in
_KEY_VARS = [v for spec in REGISTRY.values() for v in spec.env_keys] + \
    [f"{v}_2" for spec in REGISTRY.values() for v in spec.env_keys] + \
    ["APS_PROVIDER_CHAIN", "APS_MODEL_PROVIDER", "APS_ENABLE_OLLAMA"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for v in _KEY_VARS:
        monkeypatch.delenv(v, raising=False)


# ── registry integrity ───────────────────────────────────────────────────────
def test_registry_specs_are_well_formed():
    assert {"gemini", "nim", "groq", "cerebras", "openrouter"} <= set(REGISTRY)
    for name, spec in REGISTRY.items():
        assert spec.name == name
        assert spec.kind in ("openai", "gemini", "anthropic")
        assert spec.default_model
        if spec.kind == "openai":
            assert spec.base_url, f"{name}: openai-kind needs a base_url"
        if not spec.keyless:
            assert spec.env_keys, f"{name}: needs env_keys unless keyless"


def test_default_chain_is_known():
    assert all(n in REGISTRY for n in DEFAULT_CHAIN)


def test_registry_matches_settings_for_existing_providers():
    # drift guard: gemini/nim defaults mirror config.settings
    from aps.config.settings import get_settings
    s = get_settings()
    assert REGISTRY["gemini"].default_model == s.gemini_model
    assert REGISTRY["nim"].default_model == s.nim_model
    assert REGISTRY["nim"].base_url == s.nim_base_url


# ── key resolution + rotation ────────────────────────────────────────────────
def test_provider_keys_collects_and_rotates(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    assert provider_keys("groq") == ["k1", "k2"]


def test_provider_keys_dedupes_and_trims(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", " k1 ")
    monkeypatch.setenv("GROQ_API_KEY_2", "k1")     # duplicate value
    assert provider_keys("groq") == ["k1"]


def test_provider_keys_empty_without_env():
    assert provider_keys("groq") == []
    assert provider_keys("not_a_provider") == []


def test_gemini_accepts_either_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    assert provider_keys("gemini") == ["g"]


# ── availability ─────────────────────────────────────────────────────────────
def test_available_iff_key_present(monkeypatch):
    assert provider_available("groq") is False
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert provider_available("groq") is True


def test_keyless_ollama_needs_explicit_optin(monkeypatch):
    assert provider_available("ollama") is False
    monkeypatch.setenv("APS_ENABLE_OLLAMA", "true")
    assert provider_available("ollama") is True


# ── chain resolution ─────────────────────────────────────────────────────────
def test_explicit_chain_parsed_and_filtered(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq, gemini , nim")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    # nim has no key → dropped; order preserved
    assert resolved_provider_chain() == ["groq", "gemini"]


def test_unknown_names_dropped_and_deduped(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,bogus,groq")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert resolved_provider_chain() == ["groq"]


def test_back_compat_single_provider(monkeypatch):
    monkeypatch.setenv("APS_MODEL_PROVIDER", "nim")
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    assert resolved_provider_chain() == ["nim"]


def test_default_chain_when_unset_filtered_to_available(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    # DEFAULT_CHAIN = groq,cerebras,gemini,nim,openrouter → only the two with keys, in order
    assert resolved_provider_chain() == ["cerebras", "gemini"]


def test_empty_chain_when_no_keys():
    assert resolved_provider_chain() == []     # hermetic env → degrades (back-compat)
