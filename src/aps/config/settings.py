"""aps.config.settings — one switch flips the whole system between free providers.

Owned by P1. Reads .env (see .env.example). Pydantic-settings.

ODR extracted: centralized model config + per-role model variants.
Their provider switch lived in Configuration.research_model etc.; ours lives here.
"""
from __future__ import annotations

import contextvars
import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Provider/source keys the factory + tools read via raw os.getenv (NOT APS_*-prefixed,
# so pydantic-settings never maps them). An EMPTY/whitespace value for any of these is
# treated as "unset": we delete it from os.environ before load_dotenv so a blank shell
# export (e.g. `export NVIDIA_API_KEY=` in the shell that launched uvicorn) cannot SHADOW
# the real value in .env. This was the live bug — an empty NVIDIA_API_KEY shadowed the
# .env key, the factory then sent "placeholder", and every NIM call 401'd into a silent stub.
_PROVIDER_SOURCE_KEYS = (
    "NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "TAVILY_API_KEY", "APS_GITHUB_PAT", "GITHUB_PAT", "STACKEXCHANGE_KEY",
)

# Load .env into os.environ once, at first import of config. pydantic-settings only
# maps its own APS_* fields; the model factory and every source-key tool read raw
# os.getenv("NVIDIA_API_KEY" / "TAVILY_API_KEY" / ...), so they need the real env
# populated. override=False ⇒ a real (non-empty) OS env var still wins over the .env file.
#
# Skipped under pytest: the suite must stay hermetic/offline (conftest.py), so it must
# never pick up real provider keys from a local .env — that would turn unit tests into
# live network calls and break the "degrades to stub without keys" contract.
try:
    if "pytest" not in sys.modules:
        # Drop empty/whitespace keys so they don't shadow .env under override=False.
        for _k in _PROVIDER_SOURCE_KEYS:
            if not (os.environ.get(_k) or "").strip():
                os.environ.pop(_k, None)
        from dotenv import load_dotenv
        _ENV_PATH = Path(__file__).resolve().parents[3] / ".env"  # aps/.env
        load_dotenv(_ENV_PATH if _ENV_PATH.exists() else None, override=False)
except Exception:  # python-dotenv absent or unreadable .env — fall back to real env
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APS_",
        extra="ignore",
    )

    # ── provider ────────────────────────────────────────────────────────────
    # "gemini" (default, free tier) | "nim" (NVIDIA NIM, OpenAI-compatible)
    model_provider: str = "gemini"

    # Gemini free-tier model IDs (update when Google rotates free quotas).
    # 2.0-flash free tier is now limit:0 on new keys → default to 2.5-flash which still has quota.
    gemini_model: str = "gemini-2.5-flash"          # main agent model
    gemini_compression_model: str = "gemini-2.5-flash"   # ODR: separate compression model

    # NIM fallback — OpenAI-compatible endpoint.
    # nemotron-nano-9b-v2: small, free endpoint, tagged for reasoning+agentic tasks —
    # cheap enough to run the 30-call loop dozens of times while developing (recommended dev model).
    nim_model: str = "nvidia/nvidia-nemotron-nano-9b-v2"
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"

    # ── recursion / concurrency limits (TRD C1-C5) ─────────────────────────
    max_tool_calls_per_run: int = 40
    max_tool_calls_per_agent: int = 12   # ODR: max_react_tool_calls = 10
    max_concurrent_researchers: int = 3  # ODR: max_concurrent_research_units = 5
    tools_visible_per_agent: int = 20    # ADR-0005
    llm_rpm: int = 30                    # throttle model calls under NIM's ~40 RPM free cap

    # ── research depth knob (plan 1.7) ──────────────────────────────────────
    # One switch scales fan-out width + per-unit tool budget. "fast" (default) is the quick
    # demo run; "deep" matches deep-research breadth on demand (wider fan-out, more tools per
    # unit, slower). APS_RESEARCH_MODE flips it. The fast values reuse the limits above.
    research_mode: str = "fast"          # "fast" | "deep"
    deep_concurrent_researchers: int = 6
    deep_tool_calls_per_agent: int = 20

    def research_units(self) -> int:
        """Number of parallel sub-researchers for the active depth mode (1.7)."""
        return (self.deep_concurrent_researchers if self.research_mode == "deep"
                else self.max_concurrent_researchers)

    def tool_budget(self) -> int:
        """Per-unit tool-call cap for the active depth mode (1.7)."""
        return (self.deep_tool_calls_per_agent if self.research_mode == "deep"
                else self.max_tool_calls_per_agent)

    # ── research query planning (intent-based query expansion) ──────────────
    # Turn the idea into targeted, idea-anchored search phrases + sharp fan-out sub-questions so
    # retrieval asks on-topic questions (fixes keyword-scraping at the source). Off ⇒ byte-identical
    # prior behavior (no plan_queries seeding; the original generic fallback sub-topics).
    enable_query_planning: bool = True
    query_plan_count: int = 6            # target number of search phrases plan_queries emits

    # ── research relevance gate (intent filter) ─────────────────────────────
    # Score each evidence item for relevance to the idea during compression and drop the
    # off-topic before pain/competitor extraction (kills "YouTube AdBlock" surfacing for a
    # "Private Activity Tracker"). APS_ENABLE_RELEVANCE_GATE off ⇒ byte-identical prior behavior.
    enable_relevance_gate: bool = True
    relevance_min: float = 0.15          # min lexical-overlap score to keep an evidence item
    # Optional LLM refinement that rescues borderline evidence the lexical gate would drop.
    # Gated hard: only runs when enabled AND a key is present AND not under pytest (hermetic).
    enable_relevance_llm: bool = False

    # ── demo resilience ─────────────────────────────────────────────────────
    allow_fixture_fallback: bool = True

    # ── launch studio (Phase 1) ─────────────────────────────────────────────
    # Brand agent runs as a parallel graph branch; the orchestrator reads the env flag
    # APS_ENABLE_BRAND directly (default on). This is the typed surface for the same switch.
    enable_brand: bool = True

    # ── launch studio (Phase 2: legal docs) ─────────────────────────────────
    # Legal agent runs as a parallel branch off architecture (default on via APS_ENABLE_LEGAL).
    # Jurisdiction drives the cited privacy regime + employment framing (env:
    # APS_LEGAL_JURISDICTION; default India/DPDP — EU/UK/US-Delaware also supported).
    enable_legal: bool = True
    legal_jurisdiction: str = "India"

    # ── launch studio (Phase 3: funding pack) ───────────────────────────────
    # Funding agent runs as a parallel branch off execution (default on via APS_ENABLE_FUNDING):
    # pitch deck outline + illustrative financials + fundraising roadmap from existing artifacts.
    enable_funding: bool = True

    # ── launch studio (Phase 4: trademark/domain) ───────────────────────────
    # Availability agent (domain via RDAP + indicative trademark) runs as a parallel branch off
    # product; default on via APS_ENABLE_TRADEMARK. Light + heavily cached (6h TTL).
    enable_trademark: bool = True

    # ── launch studio (Phase 5: compliance) ─────────────────────────────────
    # Compliance agent runs as a parallel branch off architecture. GATED HARD — default OFF;
    # runs only when APS_ENABLE_COMPLIANCE=true. Country drives the cited privacy regime
    # (APS_COMPLIANCE_COUNTRY; falls back to legal_jurisdiction). Live guidance cached 24h.
    enable_compliance: bool = False
    compliance_country: str = ""

    # ── api auth ─────────────────────────────────────────────────────────────
    api_key: str = "dev-key"

    # ── api CORS (frontend dev origins; comma-separated) ─────────────────────
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ── per-run model override (set by the API for one run; honored over env) ─────
# A ContextVar (not a global) so concurrent runs don't clobber each other. The research
# fan-out runs sub-researchers in a ThreadPoolExecutor, which does NOT inherit context by
# default — the supervisor copies the context into each worker (contextvars.copy_context),
# so the per-run choice reaches every LLM call the run makes.
_RUN_MODEL: contextvars.ContextVar[dict | None] = contextvars.ContextVar("aps_run_model", default=None)


def set_run_model(provider: str | None = None, model: str | None = None) -> contextvars.Token:
    """Pin the provider/model for the current run (and its copied-context workers). Returns the
    ContextVar token; pass it to reset_run_model() to clear. Empty/None values are ignored."""
    return _RUN_MODEL.set({"provider": (provider or "").strip() or None,
                           "model": (model or "").strip() or None})


def reset_run_model(token: contextvars.Token) -> None:
    _RUN_MODEL.reset(token)


def run_model() -> dict | None:
    """The active per-run override ({"provider","model"}) or None."""
    return _RUN_MODEL.get()


# ── key resolution + provider auto-detect ─────────────────────────────────────

def gemini_key() -> str:
    """Usable Gemini key (empty string if none). GEMINI_API_KEY or GOOGLE_API_KEY."""
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


def nvidia_key() -> str:
    """Usable NVIDIA NIM key (empty string if none)."""
    return (os.environ.get("NVIDIA_API_KEY") or "").strip()


def resolved_provider() -> str:
    """The provider actually used for model calls.

    An explicit APS_MODEL_PROVIDER (set in the environment / .env) always wins. Otherwise,
    when the value is the bare default and exactly one provider's key is present, auto-detect
    that provider — so an NVIDIA-only environment "just works" without flipping the switch
    (and a Gemini-only one likewise), instead of defaulting to gemini and degrading.
    """
    explicit = (os.environ.get("APS_MODEL_PROVIDER") or "").strip().lower()
    if explicit:
        return explicit
    has_nim, has_gem = bool(nvidia_key()), bool(gemini_key())
    if has_nim and not has_gem:
        return "nim"
    if has_gem and not has_nim:
        return "gemini"
    return get_settings().model_provider   # default ("gemini") when 0 or 2 keys present


# ── model factory ────────────────────────────────────────────────────────────

def get_chat_model(temperature: float = 0.2, *, role: str = "default", prefer: str | None = None):
    """Return a LangChain chat model for the resolved provider.

    role: "default" | "compression"  — mirrors ODR's per-role model separation.
    Provider is a single config line (APS_MODEL_PROVIDER), with auto-detect from the
    available key when unset. Both branches support bind_tools() so the agent tool loop
    works identically on either. Raises if the resolved provider has no usable key —
    we never send a bogus placeholder that guarantees a confusing 401 (the original bug).
    """
    s = get_settings()

    # Per-run override (set by the API from POST /runs config.{provider,model}). An explicit
    # model choice pins ONE provider/model for this run, so it takes precedence over both the
    # failover chain and env resolution — the user picked exactly this model.
    ovr = run_model() or {}
    ovr_provider, ovr_model = ovr.get("provider"), ovr.get("model")

    # Multi-provider (multipleAPIplan P2): when APS_PROVIDER_CHAIN is set, ALWAYS run over the
    # FailoverChatModel. A UI/per-run pin (ovr_provider) becomes the PREFERRED head of the chain
    # (`prefer`) — so it's tried first but still FAILS OVER if exhausted, never a hard lock that
    # dies on one provider's 429. The fan-out's per-unit `prefer` works the same way.
    # No chain → the existing single gemini/nim path, byte-for-byte unchanged.
    if (os.environ.get("APS_PROVIDER_CHAIN") or "").strip():
        from aps.config.failover import build_failover_model
        return build_failover_model(temperature, role=role, prefer=(ovr_provider or prefer))

    provider = ovr_provider or resolved_provider()

    if provider == "gemini":
        # Check the key BEFORE importing the provider lib, so "raises without a key" works
        # even where the optional package isn't installed (CI runs provider-package-free).
        api_key = gemini_key()
        if not api_key:
            raise RuntimeError(
                "No Gemini key (GEMINI_API_KEY / GOOGLE_API_KEY) for APS_MODEL_PROVIDER=gemini."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_id = ovr_model or (
            s.gemini_compression_model if role == "compression" else s.gemini_model
        )
        return ChatGoogleGenerativeAI(
            model=model_id, temperature=temperature, google_api_key=api_key,
        )

    api_key = nvidia_key()
    if not api_key:
        raise RuntimeError(
            "No NVIDIA_API_KEY for APS_MODEL_PROVIDER=nim. Set it (non-empty) in .env — "
            "an empty value is treated as unset, never sent as a placeholder."
        )
    # NIM — OpenAI-compatible endpoint
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=ovr_model or s.nim_model,
        base_url=s.nim_base_url,
        api_key=api_key,
        temperature=temperature,
    )


def get_compression_model():
    """Convenience: model used in the compression/reduce node (ODR pattern)."""
    return get_chat_model(temperature=0.1, role="compression")


def describe_runtime() -> str:
    """One-line runtime summary for the startup banner: provider, model, key presence.

    Never prints the key itself — only present/MISSING — so it is safe to log.
    """
    s = get_settings()
    if (os.environ.get("APS_PROVIDER_CHAIN") or "").strip():
        from aps.config.providers import resolved_provider_chain
        chain = resolved_provider_chain()
        return f"chain={','.join(chain) or '(none available)'}"
    provider = resolved_provider()
    if provider == "gemini":
        model, present = s.gemini_model, bool(gemini_key())
    else:
        model, present = s.nim_model, bool(nvidia_key())
    return f"provider={provider} model={model} key={'present' if present else 'MISSING'}"
