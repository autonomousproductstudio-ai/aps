"""aps.config.providers — the multi-provider registry + chain resolution (multipleAPIplan P1).

Data, not behavior: a static registry of LLM providers (base URL, env vars, default model,
free-tier RPM, tool-calling support) and the logic that resolves an *ordered chain* of the
providers actually available in this environment. The model factory (a later phase) builds a
failover model over this chain; this module makes no network calls and reads keys live from
the environment so it's fully unit-testable offline.

Enabling a provider is just setting its key — no code change. Multiple keys per provider
(`GROQ_API_KEY`, `GROQ_API_KEY_2`, …) rotate to multiply free quota.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Most providers speak the OpenAI Chat Completions protocol (kind="openai" → one ChatOpenAI
# with base_url). Only a couple want a native class (kind="gemini"/"anthropic").


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    kind: str                              # "openai" | "gemini" | "anthropic"
    default_model: str
    env_keys: tuple[str, ...] = ()         # accepted env var names; first found wins, *_2.. rotate
    base_url: str | None = None            # for kind="openai"
    compression_model: str | None = None   # optional cheaper/long-context model for compression
    rpm: int = 30                          # free-tier requests/min (drives the rate limiter)
    tools: str = "true"                    # "true" | "verify" | "false" (function-calling support)
    keyless: bool = False                  # local providers (Ollama) need no key
    signup: str = ""


# ── registry (researched June 2026; see multipleAPIplan.md §3) ────────────────────────────
REGISTRY: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        # gemini-2.0-flash free tier is now limit:0 on new keys; 2.5-flash has the free quota.
        "gemini", "gemini", "gemini-2.5-flash",
        env_keys=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        compression_model="gemini-2.5-flash", rpm=15, tools="true",
        signup="https://aistudio.google.com/apikey"),
    "nim": ProviderSpec(
        "nim", "openai", "nvidia/nvidia-nemotron-nano-9b-v2",
        env_keys=("NVIDIA_API_KEY",), base_url="https://integrate.api.nvidia.com/v1",
        rpm=40, tools="true", signup="https://build.nvidia.com"),
    "groq": ProviderSpec(
        "groq", "openai", "llama-3.3-70b-versatile",
        env_keys=("GROQ_API_KEY",), base_url="https://api.groq.com/openai/v1",
        rpm=30, tools="true", signup="https://console.groq.com/keys"),
    "cerebras": ProviderSpec(
        # llama-3.3-70b is no longer exposed on the Cerebras free tier (404); gpt-oss-120b is.
        "cerebras", "openai", "gpt-oss-120b",
        env_keys=("CEREBRAS_API_KEY",), base_url="https://api.cerebras.ai/v1",
        rpm=30, tools="true", signup="https://cloud.cerebras.ai"),
    "sambanova": ProviderSpec(
        "sambanova", "openai", "Meta-Llama-3.3-70B-Instruct",
        env_keys=("SAMBANOVA_API_KEY",), base_url="https://api.sambanova.ai/v1",
        rpm=20, tools="true", signup="https://cloud.sambanova.ai"),
    "mistral": ProviderSpec(
        "mistral", "openai", "mistral-small-latest",
        env_keys=("MISTRAL_API_KEY",), base_url="https://api.mistral.ai/v1",
        rpm=2, tools="true", signup="https://console.mistral.ai"),
    "openrouter": ProviderSpec(
        "openrouter", "openai", "meta-llama/llama-3.3-70b-instruct:free",
        env_keys=("OPENROUTER_API_KEY",), base_url="https://openrouter.ai/api/v1",
        rpm=20, tools="verify", signup="https://openrouter.ai/keys"),
    "github_models": ProviderSpec(
        "github_models", "openai", "gpt-4o-mini",
        env_keys=("GITHUB_MODELS_TOKEN",), base_url="https://models.inference.ai.azure.com",
        rpm=15, tools="true", signup="https://github.com/marketplace/models"),
    "deepseek": ProviderSpec(
        "deepseek", "openai", "deepseek-chat",
        env_keys=("DEEPSEEK_API_KEY",), base_url="https://api.deepseek.com/v1",
        rpm=30, tools="true", signup="https://platform.deepseek.com"),
    "together": ProviderSpec(
        "together", "openai", "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        env_keys=("TOGETHER_API_KEY",), base_url="https://api.together.xyz/v1",
        rpm=20, tools="true", signup="https://api.together.ai"),
    "xai": ProviderSpec(
        "xai", "openai", "grok-2-latest",
        env_keys=("XAI_API_KEY",), base_url="https://api.x.ai/v1",
        rpm=20, tools="true", signup="https://x.ai/api"),
    "openai": ProviderSpec(
        "openai", "openai", "gpt-4o-mini",
        env_keys=("OPENAI_API_KEY",), base_url="https://api.openai.com/v1",
        rpm=60, tools="true", signup="https://platform.openai.com"),
    "anthropic": ProviderSpec(
        "anthropic", "anthropic", "claude-3-5-haiku-latest",
        env_keys=("ANTHROPIC_API_KEY",), rpm=50, tools="true",
        signup="https://console.anthropic.com"),
    # ── self-hosted / local (OpenAI-compatible servers; no key, opt in with
    #    APS_ENABLE_<NAME>=true; override port/model via APS_<NAME>_BASE_URL / APS_<NAME>_MODEL) ──
    "ollama": ProviderSpec(
        "ollama", "openai", "llama3.1",
        base_url="http://localhost:11434/v1", rpm=120, tools="verify", keyless=True,
        signup="https://ollama.com"),
    "lmstudio": ProviderSpec(
        "lmstudio", "openai", "local-model",
        base_url="http://localhost:1234/v1", rpm=120, tools="verify", keyless=True,
        signup="https://lmstudio.ai"),
    "vllm": ProviderSpec(
        "vllm", "openai", "Qwen/Qwen3-32B",
        base_url="http://localhost:8000/v1", rpm=240, tools="verify", keyless=True,
        signup="https://github.com/vllm-project/vllm"),
    "localai": ProviderSpec(
        "localai", "openai", "gpt-4",
        base_url="http://localhost:8080/v1", rpm=120, tools="verify", keyless=True,
        signup="https://localai.io"),
    "llamacpp": ProviderSpec(
        "llamacpp", "openai", "local-model",
        base_url="http://localhost:8080/v1", rpm=120, tools="verify", keyless=True,
        signup="https://github.com/ggml-org/llama.cpp"),
}

# Default priority chain when neither APS_PROVIDER_CHAIN nor APS_MODEL_PROVIDER is set:
# fast + generous + reliably tool-capable first, the proven current paths next, catch-all last.
DEFAULT_CHAIN: tuple[str, ...] = ("groq", "cerebras", "gemini", "nim", "openrouter")

_ROTATE = range(2, 6)   # GROQ_API_KEY_2 .. _5


def provider_keys(name: str) -> list[str]:
    """All non-empty keys for a provider, in order, with rotation suffixes, deduped.

    e.g. GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3 → multiply the free quota.
    """
    spec = REGISTRY.get(name)
    if spec is None:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for env in spec.env_keys:
        for var in (env, *(f"{env}_{i}" for i in _ROTATE)):
            v = (os.environ.get(var) or "").strip()
            if v and v not in seen:
                seen.add(v)
                out.append(v)
    return out


def provider_available(name: str) -> bool:
    """True if this provider can be used now: it has a key, or it's a keyless self-hosted
    provider explicitly enabled via APS_ENABLE_<NAME> (e.g. APS_ENABLE_VLLM=true). The actual
    reachability of a local server is handled by failover — an unreachable one just fails over."""
    spec = REGISTRY.get(name)
    if spec is None:
        return False
    if spec.keyless:
        return (os.environ.get(f"APS_ENABLE_{name.upper()}") or "").strip().lower() in ("1", "true", "yes")
    return bool(provider_keys(name))


def resolved_provider_chain() -> list[str]:
    """The ordered list of available providers to try, highest priority first.

    Priority of configuration:
      1. APS_PROVIDER_CHAIN="groq,gemini,nim"  — explicit, ordered (the multi-provider switch)
      2. APS_MODEL_PROVIDER=<one>              — back-compat single provider
      3. DEFAULT_CHAIN
    Every source is filtered to providers that are known AND available; order/dupes preserved.
    """
    raw_chain = (os.environ.get("APS_PROVIDER_CHAIN") or "").strip()
    if raw_chain:
        names = [n.strip().lower() for n in raw_chain.split(",") if n.strip()]
    else:
        single = (os.environ.get("APS_MODEL_PROVIDER") or "").strip().lower()
        names = [single] if single else list(DEFAULT_CHAIN)

    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        if n in REGISTRY and n not in seen and provider_available(n):
            seen.add(n)
            out.append(n)
    return out
