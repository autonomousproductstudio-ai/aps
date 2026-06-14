"""LLM-provider rate limiting (Req-4). NOT a counted tool — platform capability.

Free model endpoints cap requests/minute (NIM ~40 RPM; Gemini free quota). `infra/http`
only throttles retrieval *hosts* — model calls go through LangChain and were unthrottled.
That bites once research fan-out fires `plan_subtopics` + N parallel sub-researchers
concurrently: a burst sails past the cap and 429s mid-demo.

`acquire_llm()` blocks just long enough to stay under `settings.llm_rpm` before each model
invoke. It reuses the same token-bucket as the HTTP limiter and is thread-safe (the fan-out
runs sub-researchers in a ThreadPoolExecutor). Pair it with `with_retry` so a 429 is both
throttled ahead of time and backed off if it still slips through.
"""
from __future__ import annotations

import os

from aps.infra.rate_limiter import RateLimiter
from aps.infra.logging import get_logger
from aps.config.settings import get_settings, resolved_provider, nvidia_key, gemini_key

_LOG = get_logger("aps.llm")
_LIMITER: RateLimiter | None = None
_CONFIGURED: set[str] = set()   # provider buckets whose per-provider rpm has been applied


def _limiter() -> RateLimiter:
    global _LIMITER
    if _LIMITER is None:
        _LIMITER = RateLimiter(rpm=get_settings().llm_rpm)   # default for non-provider sources
    return _LIMITER


def _provider_rpm(source: str) -> int | None:
    """Per-provider RPM: an APS_<PROVIDER>_RPM override, else the registry's free-tier rpm.
    None for the generic "llm" source → it uses the default bucket (settings.llm_rpm)."""
    env = (os.environ.get(f"APS_{source.upper()}_RPM") or "").strip()
    if env.isdigit():
        return int(env)
    from aps.config.providers import REGISTRY
    spec = REGISTRY.get(source)
    return spec.rpm if spec else None


def acquire_llm(source: str = "llm") -> float:
    """Block to honor the RPM cap before a model call (multipleAPIplan P3).

    Each provider gets its OWN bucket sized to its free-tier rpm (Gemini 15, Groq 30, …), so
    one provider's cap can't throttle another and the research fan-out can spread across
    providers without 429-ing the head one. The generic "llm" source keeps the global cap.
    """
    lim = _limiter()
    if source not in _CONFIGURED:
        rpm = _provider_rpm(source)
        if rpm is not None:
            lim.configure(source, rpm)
        _CONFIGURED.add(source)
    waited = lim.acquire(source)
    if waited > 0:
        _LOG.debug("llm_rate_limit_wait", seconds=round(waited, 2), source=source)
    return waited


def has_llm_key() -> bool:
    """True if a usable key for the RESOLVED provider is present.

    Multi-provider (multipleAPIplan P2): when APS_PROVIDER_CHAIN is set, "has a key" means the
    resolved chain has at least one available provider. Otherwise the single gemini/nim check
    (empty/whitespace counts as absent — the second line of defense for the silent-401 bug).
    """
    if (os.environ.get("APS_PROVIDER_CHAIN") or "").strip():
        from aps.config.providers import resolved_provider_chain
        return bool(resolved_provider_chain())
    return bool(nvidia_key()) if resolved_provider() == "nim" else bool(gemini_key())


def key_mismatch() -> str | None:
    """If the resolved provider has no key but the OTHER provider does, return a specific
    remedy message; else None. Surfaces the classic 'NVIDIA key set, provider on gemini'
    (or vice-versa) misconfig as a loud, actionable error instead of a silent degrade.

    Not applicable under a multi-provider chain (failover handles a per-provider miss)."""
    if (os.environ.get("APS_PROVIDER_CHAIN") or "").strip():
        return None
    provider = resolved_provider()
    if provider == "nim" and not nvidia_key() and gemini_key():
        return ("APS_MODEL_PROVIDER=nim but NVIDIA_API_KEY is empty/missing; a Gemini key IS "
                "set — set a real NVIDIA_API_KEY or APS_MODEL_PROVIDER=gemini.")
    if provider == "gemini" and not gemini_key() and nvidia_key():
        return ("APS_MODEL_PROVIDER=gemini but GEMINI_API_KEY/GOOGLE_API_KEY is empty/missing; "
                "an NVIDIA key IS set — set a real Gemini key or APS_MODEL_PROVIDER=nim.")
    return None


def preflight_check() -> tuple[bool, str | None]:
    """Validate the LLM provider is usable before a run.

    - Provider/key mismatch (e.g. provider=nim but only a Gemini key) -> (False, remedy) with
      NO network call — a loud, specific misconfig the caller fails fast on.
    - No key set at all -> (False, "no LLM key set") with NO network call (keeps offline/CI
      hermetic; the caller treats this as the keyless degrade path, not a hard failure).
    - Key present -> one tiny ping; (True, None) on success, (False, <error>) on failure
      (e.g. a 401 from a wrong/expired key) so the caller can fail fast instead of running
      the whole pipeline and silently degrading to the fixture.
    """
    mismatch = key_mismatch()
    if mismatch:
        return (False, mismatch)
    if not has_llm_key():
        return (False, "no LLM key set")
    try:
        from aps.config.settings import get_chat_model
        from langchain_core.messages import HumanMessage
        get_chat_model(temperature=0).invoke([HumanMessage("ping")])
        return (True, None)
    except Exception as e:
        return (False, f"{type(e).__name__}: {str(e)[:160]}")
