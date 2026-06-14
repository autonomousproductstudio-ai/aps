"""aps.agents.research.supervisor — research fan-out/collect (the CEO's research delegate).

Forks ODR's supervisor pattern: a lead-researcher LLM call decomposes the idea into a few
distinct research angles, then fans out one sub-researcher per angle IN PARALLEL — each an
isolated `gather_evidence` run with its own focus-scoped context and the scoped tool set —
and collects their typed partials into ONE compressed `ResearchReturn`.

ODR runs its sub-researchers with `asyncio.gather` inside a node; our stack is synchronous
(`requests` + `bound.invoke`), so the faithful analog is a `ThreadPoolExecutor` over the
same I/O-bound work — real parallelism without rewriting the sync tool layer.

A subagent here = isolated context + scoped tools + typed return. That is the contract,
implemented as threaded units faithful to ODR's gather (not the LangGraph `Send` API).
"""
from __future__ import annotations

import contextvars
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from aps.config.settings import get_chat_model, get_settings
from aps.config.providers import resolved_provider_chain
from aps.state.models import Evidence, ResearchReturn
from aps.agents.research.agent import gather_evidence, _compress
from aps.infra.llm import acquire_llm


def unit_providers(n: int) -> list[str | None]:
    """Assign a provider to each of N sub-researchers (multipleAPIplan P10 — diversification).

    In multi-provider mode (APS_PROVIDER_CHAIN set) with ≥2 available providers, round-robin
    the chain across the units so they run on DIFFERENT providers' quotas in parallel —
    ~N× effective throughput and no single-provider 429. Otherwise every unit uses the default
    model (returns None per unit). Deterministic → reproducible runs and tests.
    """
    # Opt-out: APS_RESEARCH_DIVERSIFY=false makes every sub-researcher use the chain head (e.g. a
    # reliable paid OpenAI primary) + failover, instead of spreading across providers. Best when
    # one provider has ample quota — research starts from it and never lands on an exhausted free one.
    if (os.environ.get("APS_RESEARCH_DIVERSIFY") or "true").strip().lower() != "true":
        return [None] * n
    if not (os.environ.get("APS_PROVIDER_CHAIN") or "").strip():
        return [None] * n
    chain = resolved_provider_chain()
    if len(chain) < 2:
        return [None] * n
    # P8 router: order the pool best-fit-first for a tool-using research task, weighted by
    # remaining quota headroom (least-used first) — then round-robin so the units still spread
    # across DISTINCT providers. Deterministic.
    from aps.config.router import route, RESEARCH
    from aps.config.quota import LEDGER
    pool = route(RESEARCH, chain, LEDGER.snapshot())
    return [pool[i % len(pool)] for i in range(n)]

# Sharpened lead-researcher prompt (adapted from ODR open_deep_research `lead_researcher_prompt`
# + claude-cookbooks `research_lead_agent.md`): each delegated unit must be a SPECIFIC, standalone
# sub-question that NAMES this idea's domain/audience/problem — not a vague category label, which
# is what makes a sub-researcher issue on-topic queries instead of keyword-scraping.
_PLAN_SYSTEM = (
    "You are a lead research strategist for a startup studio. Decompose the product idea into "
    "distinct, non-overlapping research SUB-QUESTIONS that separate junior researchers can each "
    "own. Each line must be a specific, standalone task that NAMES this idea's actual domain, "
    "audience, and problem — never a bare category. One core objective per line; be very clear "
    "and specific.\n"
    "Example — idea 'Private Activity Tracker':\n"
    "find user complaints about existing privacy-focused activity/time trackers\n"
    "find self-hosted and open-source activity-tracker competitors and their gaps\n"
    "find demand signals: HN/Reddit threads asking for a private, local-first tracker\n"
    "Now do the same for the given idea. Reply with ONE sub-question per line, at most {k} lines, "
    "no numbering and no extra prose."
)


def _idea_core(idea: str) -> str:
    """A short, clean noun phrase for the idea, for templating fallback queries/sub-questions."""
    try:
        from aps.tools.analysis._text import clean_label
        core = clean_label(idea, max_words=8, max_chars=64).rstrip(".")
        return core or (idea or "").strip()
    except Exception:
        return (idea or "").strip()


# The pre-query-planning generic decomposition — used only when query planning is disabled
# (APS_ENABLE_QUERY_PLANNING=false), so flag-off reproduces the exact prior fan-out.
_GENERIC_SUBTOPICS = [
    "user pain points & complaints with existing solutions",
    "competitors, their features & pricing",
    "market size & demand signals",
]


def _fallback_subtopics(idea: str, k: int) -> list[str]:
    """Decomposition used when planning has no key / fails (e.g. under pytest).

    With query planning on (default), interpolates the idea core so even the no-LLM path delegates
    SHARP sub-questions; off ⇒ the original generic list (byte-identical prior behavior). Exactly 3
    load-bearing angles (pains / competitors / demand) ordered so a `[:k]` cut never drops one.
    """
    if not getattr(get_settings(), "enable_query_planning", True):
        return _GENERIC_SUBTOPICS[:k]
    core = _idea_core(idea)
    return [
        f"user complaints and pain points with existing {core} tools",
        f"competitors and alternatives to {core}, their features, pricing and gaps",
        f"market size and demand signals for {core} (HN/Reddit/forum threads, jobs)",
    ][:k]


# Adapted from ODR local-deep-researcher `query_writer_instructions`: turn ONE idea into several
# targeted search phrases (we keep it line-based, not JSON, so small/free models parse reliably).
_QUERY_SYSTEM = (
    "You are a search strategist. Given a product idea, write {n} specific web-search phrases that "
    "would surface REAL evidence about it — covering the product's domain, its target audience, "
    "direct competitors and alternatives, and user complaints about existing solutions. Each phrase "
    "must be concrete and anchored to THIS idea (name the actual thing), not a generic keyword.\n"
    "Example — idea 'Private Activity Tracker': self-hosted activity tracker; privacy-first time "
    "tracking app; open-source screen-time monitor; local-first productivity logger; complaints "
    "about activity trackers selling data.\n"
    "Reply with ONE phrase per line, at most {n} lines, no numbering and no extra prose."
)


def _fallback_queries(idea: str, n: int) -> list[str]:
    """Deterministic, idea-anchored search phrases for the no-key/pytest path (and the keyless
    retriever). Templates the idea core so the no-LLM path still asks on-topic questions instead
    of a single bare token-query. Deduped, order-stable, never empty."""
    core = _idea_core(idea)
    raw = idea.strip() or core
    cands = [
        raw,
        f"self-hosted {core}",
        f"open source {core}",
        f"{core} alternatives",
        f"best {core} tools",
        f"complaints about {core}",
        f"{core} pricing",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for q in cands:
        q = q.strip()
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            out.append(q)
    return out[:n] or [raw]


def plan_queries(idea: str, *, n: int | None = None) -> list[str]:
    """Turn the idea into N targeted search phrases via one cheap LLM call (ODR query-writer).

    Anchors retrieval to the idea's domain/audience/competitors/complaints so the tools are asked
    on-topic questions. Falls back to `_fallback_queries` on any failure / no key / under pytest,
    so it's hermetic and works on the keyless path. Deduped, capped to n, never empty.
    """
    s = get_settings()
    n = n or getattr(s, "query_plan_count", 6)
    if not getattr(s, "enable_query_planning", True):
        return _fallback_queries(idea, n)
    try:
        acquire_llm()
        resp = get_chat_model().invoke([
            SystemMessage(_QUERY_SYSTEM.format(n=n)),
            HumanMessage(f"Product idea: {idea}"),
        ])
        text = resp.content if hasattr(resp, "content") else str(resp)
        out: list[str] = []
        seen: set[str] = set()
        for ln in str(text).splitlines():
            q = ln.strip(" -*•\t").strip().strip('"')
            key = q.lower()
            if len(q) >= 4 and key not in seen:
                seen.add(key)
                out.append(q)
        return out[:n] or _fallback_queries(idea, n)
    except Exception:
        return _fallback_queries(idea, n)


def _emit(on_event: Callable | None, type_: str, data: dict) -> None:
    if on_event:
        try:
            on_event(type_, data)
        except Exception:
            pass


def plan_subtopics(idea: str, *, k: int | None = None) -> list[str]:
    """Decompose the idea into <=k distinct research angles via one LLM call.

    Falls back to a fixed 3-angle decomposition on any failure / junk output. The result
    is de-duped and capped to k so the fan-out never exceeds the concurrency budget; a
    model returning more than k angles is a deliberate, capped cut (not silent truncation).
    """
    s = get_settings()
    k = k or s.research_units()          # depth knob (plan 1.7): fast=3, deep=6
    try:
        acquire_llm()                                     # throttle under the free RPM cap
        resp = get_chat_model().invoke([
            SystemMessage(_PLAN_SYSTEM.format(k=k)),
            HumanMessage(f"Product idea: {idea}"),
        ])
        text = resp.content if hasattr(resp, "content") else str(resp)
        lines = [ln.strip(" -*•\t").strip() for ln in str(text).splitlines()]
        seen: set[str] = set()
        out: list[str] = []
        for ln in lines:
            if len(ln) < 6:
                continue
            key = ln.lower()
            if key not in seen:
                seen.add(key)
                out.append(ln)
        out = out[:k]
        return out or _fallback_subtopics(idea, k)
    except Exception:
        return _fallback_subtopics(idea, k)


def run_research_fanout(idea: str, on_event: Callable | None = None) -> ResearchReturn:
    """Plan → parallel sub-researchers → single compression. Returns a typed brief.

    Each unit is an isolated `gather_evidence(idea, focus=topic)` run, executed in parallel
    via a ThreadPoolExecutor (sync analog of ODR's asyncio.gather), capped at
    `max_concurrent_researchers`. A per-unit failure degrades to `[]` and never kills the
    run; compression then dedupes/ranks over the union (cross-unit duplicates collapse).
    """
    s = get_settings()
    units = plan_subtopics(idea)
    _emit(on_event, "research_plan", {"subtopics": units})

    # Holds the last underlying unit failure so we can re-raise its REAL cause (e.g. an auth
    # error or a missing-key RuntimeError) when nothing was gathered — otherwise the
    # orchestrator only sees a generic "no evidence" and can't classify WHY it degraded.
    last_error: list[str] = []

    def _unit(topic: str, provider: str | None) -> tuple[list[Evidence], int]:
        _emit(on_event, "research_unit_start", {"focus": topic, "provider": provider})
        try:
            ev, n = gather_evidence(idea, focus=topic, provider=provider)
        except Exception as e:  # degrade this unit, keep the fan-out alive
            last_error.append(str(e))
            _emit(on_event, "error",
                  {"agent": "research_unit", "focus": topic, "provider": provider,
                   "error": str(e)[:200]})
            ev, n = [], 0
        _emit(on_event, "research_unit_end",
              {"focus": topic, "provider": provider, "evidence": len(ev)})
        return ev, n

    # P10: spread the units across providers (different free-tier quotas, in parallel).
    assigned = unit_providers(len(units))
    if any(assigned):
        _emit(on_event, "research_diversified", {"providers": assigned})

    # Carry the run's ContextVars (esp. the per-run model override set by the API) into each
    # worker thread: ThreadPoolExecutor does NOT inherit context. Copy it once PER unit on this
    # (run) thread — each copy already holds _RUN_MODEL — and .run() each exactly once in a
    # worker (a Context can't be entered concurrently, hence one copy per task).
    ctxs = [contextvars.copy_context() for _ in units]

    def _run_unit(ctx: contextvars.Context, topic: str, provider: str | None):
        return ctx.run(_unit, topic, provider)

    merged: list[Evidence] = []
    total_calls = 0
    with ThreadPoolExecutor(max_workers=max(1, s.research_units())) as pool:
        for ev, n in pool.map(_run_unit, ctxs, units, assigned):
            merged.extend(ev)
            total_calls += n

    # Empty-merge guard: if every unit came back empty (e.g. all 429'd / no key), retry once
    # on the single-unit path; if STILL empty, raise the real underlying cause so the
    # orchestrator degrades with a precise reason (never a schema-valid-but-hollow PRD).
    if not merged:
        _emit(on_event, "error",
              {"agent": "research", "error": "fan-out produced no evidence; retrying single-unit"})
        try:
            ev, n = gather_evidence(idea)
            merged.extend(ev)
            total_calls += n
        except Exception as e:
            last_error.append(str(e))
            _emit(on_event, "error", {"agent": "research", "error": str(e)[:200]})
        if not merged:
            _emit(on_event, "error",
                  {"agent": "research", "error": "no evidence after single-unit retry"})
            # Re-raise the real cause (auth / missing key / network) so it can be classified.
            raise RuntimeError(last_error[-1] if last_error else "research produced no evidence")

    result = _compress(idea, merged)
    result.tool_calls = total_calls
    return result
