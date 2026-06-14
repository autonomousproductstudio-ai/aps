"""aps.config.router — capability-based provider routing (multipleAPIplan P8).

A transparent, DETERMINISTIC policy (no ML, no randomness → reproducible) that, given a task's
requirements, orders the available providers best-fit first. Composes with failover: `route()`
decides the *order*, the FailoverChatModel handles a provider that still errors.

`route()` is a pure function over (profile, available providers, a load snapshot) — trivially
unit-testable. It's wired lightly: the research fan-out uses it to order its diversification
pool by fit before round-robin.
"""
from __future__ import annotations

from dataclasses import dataclass

from aps.config.providers import REGISTRY

# 0–3 capability scores per provider on the axes that matter (multipleAPIplan §12).
# Editable data; the live smoke (scripts/live_providers_smoke.py) is the source of truth for
# whether a model actually tool-calls.
CAPABILITY: dict[str, dict[str, int]] = {
    "groq":      {"tools": 3, "reasoning": 2, "speed": 3, "context": 2},
    "cerebras":  {"tools": 3, "reasoning": 2, "speed": 3, "context": 2},
    "gemini":    {"tools": 3, "reasoning": 3, "speed": 2, "context": 3},
    "nim":       {"tools": 3, "reasoning": 2, "speed": 2, "context": 2},
    "sambanova": {"tools": 3, "reasoning": 2, "speed": 2, "context": 2},
    "openai":    {"tools": 3, "reasoning": 3, "speed": 2, "context": 3},
    "anthropic": {"tools": 3, "reasoning": 3, "speed": 2, "context": 3},
    "mistral":   {"tools": 2, "reasoning": 2, "speed": 2, "context": 2},
    "deepseek":  {"tools": 3, "reasoning": 3, "speed": 2, "context": 2},
    "together":  {"tools": 3, "reasoning": 2, "speed": 2, "context": 2},
    "xai":       {"tools": 3, "reasoning": 3, "speed": 2, "context": 2},
    "openrouter": {"tools": 2, "reasoning": 2, "speed": 2, "context": 2},
    "github_models": {"tools": 3, "reasoning": 2, "speed": 2, "context": 2},
    "ollama":    {"tools": 2, "reasoning": 1, "speed": 1, "context": 1},
    "lmstudio":  {"tools": 2, "reasoning": 1, "speed": 1, "context": 1},
    "vllm":      {"tools": 2, "reasoning": 2, "speed": 2, "context": 2},
    "localai":   {"tools": 2, "reasoning": 1, "speed": 1, "context": 1},
    "llamacpp":  {"tools": 2, "reasoning": 1, "speed": 1, "context": 1},
}
_DEFAULT_CAPS = {"tools": 2, "reasoning": 2, "speed": 2, "context": 2}


@dataclass(frozen=True)
class TaskProfile:
    needs_tools: bool = False
    complexity: str = "med"     # low | med | high  (weights reasoning)
    context: str = "short"      # short | long      (hard-requires context≥3 when long)
    latency: str = "med"        # low | med | high  (low = prefer fast)


# common call sites
PLAN = TaskProfile(needs_tools=False, complexity="high", latency="low")
RESEARCH = TaskProfile(needs_tools=True, complexity="med", latency="med")
COMPRESSION = TaskProfile(needs_tools=False, complexity="low", context="long")


def _caps(name: str) -> dict[str, int]:
    return CAPABILITY.get(name, _DEFAULT_CAPS)


def _eligible(name: str, profile: TaskProfile) -> bool:
    c = _caps(name)
    if profile.needs_tools and c["tools"] < 2:
        return False
    if profile.context == "long" and c["context"] < 3:
        return False
    return True


def _score(name: str, profile: TaskProfile, load: dict[str, int]) -> float:
    c = _caps(name)
    reasoning_w = {"low": 0.2, "med": 0.6, "high": 1.2}[profile.complexity]
    speed_w = {"low": 1.2, "med": 0.6, "high": 0.3}[profile.latency]   # low latency ⇒ value speed
    fit = c["tools"] * (1.0 if profile.needs_tools else 0.3) + c["reasoning"] * reasoning_w \
        + c["speed"] * speed_w + c["context"] * (0.8 if profile.context == "long" else 0.2)
    # quota headroom: fewer prior calls ⇒ higher (spread load deterministically)
    rpm = REGISTRY[name].rpm if name in REGISTRY else 30
    headroom = max(0.0, 1.0 - load.get(name, 0) / max(rpm, 1))
    return round(fit + 1.5 * headroom, 4)


def route(profile: TaskProfile, available: list[str], load: dict[str, int] | None = None) -> list[str]:
    """Order `available` providers best-fit-first for `profile`. Drops providers that fail the
    profile's hard requirements (e.g. no tool-calling for a tool task). Stable + deterministic
    (ties broken by the input order)."""
    load = load or {}
    eligible = [p for p in available if _eligible(p, profile)]
    # if NOTHING is eligible (e.g. only no-tool providers for a tool task), fall back to the
    # original order rather than returning empty — failover + the model's own behavior decide.
    pool = eligible or list(available)
    indexed = list(enumerate(pool))
    indexed.sort(key=lambda iv: (-_score(iv[1], profile, load), iv[0]))
    return [name for _, name in indexed]
