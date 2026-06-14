"""aps.config.failover — FailoverChatModel over the provider chain (multipleAPIplan P2).

A thin LangChain-compatible wrapper around an ORDERED list of provider runtimes. It forwards
`bind_tools` and `invoke`; on a **retryable** error (429 / 5xx / timeout / connection / auth /
provider-lib-not-installed) it advances to the next provider — so a single API being rate-
limited, down, or keyless never sinks a run. A non-retryable error (a real content/validation
bug) raises immediately, instead of masking it by trying every provider.

Opt-in: `get_chat_model()` returns this only when `APS_PROVIDER_CHAIN` is set; otherwise the
existing single-provider path is used unchanged (back-compat). The agents call
`get_chat_model()`/`bind_tools()`/`invoke()` exactly as before and never know the difference.
"""
from __future__ import annotations

import os

from aps.config.providers import REGISTRY, provider_keys, resolved_provider_chain
from aps.infra.logging import get_logger

_LOG = get_logger("aps.failover")

# Substrings / exception-name fragments that mark a transient, quota, or auth failure —
# i.e. "try the next provider", not "this request is malformed".
_RETRY_MARKERS = (
    "429", "rate limit", "ratelimit", "quota", "exceeded", "timeout", "timed out",
    "connection", "unavailable", "overloaded", "temporarily", "500", "502", "503", "504",
    "401", "403", "unauthorized", "authentication", "permission denied", "invalid api key",
)
_RETRY_TYPES = ("timeout", "connection", "ratelimit", "apistatus", "apiconnection",
                "serviceunavailable", "internalserver")


def base_url_for(spec) -> str | None:
    """Resolved base URL for an openai-compatible provider: APS_<NAME>_BASE_URL override
    (so a self-hosted LM Studio / vLLM / LocalAI / llama.cpp server can point anywhere),
    else the registry default."""
    return (os.environ.get(f"APS_{spec.name.upper()}_BASE_URL") or "").strip() or spec.base_url


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ImportError):      # provider package not installed → skip to next
        return True
    blob = (str(exc) or "").lower()
    if any(m in blob for m in _RETRY_MARKERS):
        return True
    name = type(exc).__name__.lower()
    return any(k in name for k in _RETRY_TYPES)


class ProviderRuntime:
    """One provider in the chain: builds its LangChain chat model lazily (no network until
    the model is actually invoked)."""

    def __init__(self, spec, key: str, temperature: float, role: str) -> None:
        self.spec = spec
        self.name = spec.name
        self._key = key
        self._t = temperature
        self._role = role
        self._model = None

    def _model_id(self) -> str:
        spec = self.spec
        mid = (spec.compression_model if self._role == "compression" and spec.compression_model
               else spec.default_model)
        return (os.environ.get(f"APS_{spec.name.upper()}_MODEL") or "").strip() or mid

    def chat_model(self):
        if self._model is not None:
            return self._model
        spec, model_id = self.spec, self._model_id()
        if spec.kind == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            self._model = ChatGoogleGenerativeAI(
                model=model_id, temperature=self._t, google_api_key=self._key)
        elif spec.kind == "anthropic":
            from langchain_anthropic import ChatAnthropic
            self._model = ChatAnthropic(model=model_id, temperature=self._t, api_key=self._key)
        else:  # openai-compatible (the majority, incl. self-hosted local servers)
            from langchain_openai import ChatOpenAI
            # APS_<NAME>_BASE_URL lets a self-hosted server (LM Studio :1234, vLLM :8000,
            # LocalAI/llama.cpp :8080, …) override the registry default per machine.
            self._model = ChatOpenAI(model=model_id, base_url=base_url_for(spec),
                                     api_key=self._key or "local", temperature=self._t)
        return self._model


class FailoverChatModel:
    """LangChain-ish model that tries each provider runtime in order, failing over on
    retryable errors. Exposes the subset the agents use: `bind_tools` and `invoke`."""

    def __init__(self, runtimes: list[ProviderRuntime], bound_tools=None, bind_kwargs=None) -> None:
        self._runtimes = runtimes
        self._bound_tools = bound_tools
        self._bind_kwargs = bind_kwargs or {}
        self.last_provider: str | None = None

    def bind_tools(self, tools, **kwargs) -> "FailoverChatModel":
        # carry the tools; each provider gets them bound at invoke time (lazy, per-provider)
        return FailoverChatModel(self._runtimes, tools, kwargs)

    @property
    def providers(self) -> list[str]:
        return [r.name for r in self._runtimes]

    def invoke(self, messages, **kwargs):
        from aps.infra.llm import acquire_llm   # lazy: avoids an import cycle at module load
        from aps.infra.metrics import record_llm_call
        from aps.config.quota import LEDGER, BREAKER
        from aps.config.portable import normalize_history

        # P9 circuit breaker: providers that are NOT cooling down go first, benched ones last
        # (stable sort preserves chain order within each group; if all are open we still try).
        runtimes = sorted(self._runtimes, key=lambda r: BREAKER.is_open(r.name))
        last_exc: Exception | None = None
        n = len(runtimes)
        for i, rt in enumerate(runtimes):
            try:
                acquire_llm(rt.name)            # per-provider throttle (P3 gives each its own rpm)
                model = rt.chat_model()
                if self._bound_tools is not None:
                    model = model.bind_tools(self._bound_tools, **self._bind_kwargs)
                # P7 portable context: canonicalize tool_call ids so this provider accepts a
                # history a previous provider may have started (no-op when there are no tools).
                out = model.invoke(normalize_history(messages, getattr(rt, "spec", None)), **kwargs)
                self.last_provider = rt.name
                LEDGER.record(rt.name)          # P9 load signal for the router
                record_llm_call(rt.name, ok=True)   # P5 metric
                _LOG.debug("llm_provider_used", provider=rt.name)
                return out
            except Exception as e:             # noqa: BLE001 — classified by _is_retryable
                last_exc = e
                if _is_retryable(e):
                    BREAKER.trip(rt.name)       # P9: bench it so the chain routes around it
                    record_llm_call(rt.name, ok=False)   # P5: count the failover
                    if i < n - 1:
                        _LOG.warning("llm_provider_failover", provider=rt.name,
                                     next=runtimes[i + 1].name, error=str(e)[:160])
                        continue
                raise
        assert last_exc is not None            # unreachable (n>=1 guaranteed by builder)
        raise last_exc


def build_failover_model(temperature: float = 0.2, *, role: str = "default",
                         prefer: str | None = None) -> FailoverChatModel:
    """Build a FailoverChatModel over the resolved provider chain. Raises (like the single-
    provider factory) when no provider is available, so the orchestrator's degrade path fires.

    `prefer` (P10 diversification) moves one provider to the HEAD of the chain so this model
    primarily uses it, while keeping the rest as failover backups. The research fan-out passes
    a different `prefer` per sub-researcher so N units spread across N providers' quotas.
    """
    chain = resolved_provider_chain()
    if not chain:
        raise RuntimeError(
            "No LLM provider available for APS_PROVIDER_CHAIN — set at least one provider key "
            "(see multipleAPIplan.md appendix) or unset APS_PROVIDER_CHAIN to use the single "
            "gemini/nim path.")
    if prefer and prefer in chain:
        chain = [prefer] + [p for p in chain if p != prefer]
    runtimes = []
    for name in chain:
        keys = provider_keys(name)
        runtimes.append(ProviderRuntime(REGISTRY[name], keys[0] if keys else "", temperature, role))
    return FailoverChatModel(runtimes)
