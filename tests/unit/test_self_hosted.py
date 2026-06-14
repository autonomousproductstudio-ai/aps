"""Self-hosted / local OpenAI-compatible providers (LM Studio · vLLM · LocalAI · llama.cpp)."""
from __future__ import annotations

import pytest

from aps.config.providers import REGISTRY, provider_available, resolved_provider_chain
from aps.config.failover import base_url_for

_LOCAL = ("ollama", "lmstudio", "vllm", "localai", "llamacpp")
_ENV = [f"APS_ENABLE_{p.upper()}" for p in _LOCAL] + \
    [f"APS_{p.upper()}_BASE_URL" for p in _LOCAL] + ["APS_PROVIDER_CHAIN", "GROQ_API_KEY"]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for v in _ENV:
        monkeypatch.delenv(v, raising=False)


def test_local_providers_registered():
    for name in _LOCAL:
        spec = REGISTRY[name]
        assert spec.kind == "openai" and spec.keyless and spec.base_url.startswith("http://localhost")


def test_local_default_ports():
    assert REGISTRY["lmstudio"].base_url.endswith(":1234/v1")
    assert REGISTRY["vllm"].base_url.endswith(":8000/v1")
    assert REGISTRY["localai"].base_url.endswith(":8080/v1")


@pytest.mark.parametrize("name", _LOCAL)
def test_local_needs_explicit_optin(name, monkeypatch):
    assert provider_available(name) is False
    monkeypatch.setenv(f"APS_ENABLE_{name.upper()}", "true")
    assert provider_available(name) is True


def test_base_url_override_per_machine(monkeypatch):
    assert base_url_for(REGISTRY["vllm"]) == "http://localhost:8000/v1"   # default
    monkeypatch.setenv("APS_VLLM_BASE_URL", "http://192.168.1.50:8000/v1")
    assert base_url_for(REGISTRY["vllm"]) == "http://192.168.1.50:8000/v1"


def test_local_provider_joins_the_chain(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "vllm,groq")
    monkeypatch.setenv("APS_ENABLE_VLLM", "true")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert resolved_provider_chain() == ["vllm", "groq"]   # local first, cloud failover behind it


def test_build_failover_includes_local(monkeypatch):
    from aps.config.failover import build_failover_model, FailoverChatModel
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "lmstudio")
    monkeypatch.setenv("APS_ENABLE_LMSTUDIO", "true")
    m = build_failover_model()
    assert isinstance(m, FailoverChatModel) and m.providers == ["lmstudio"]
