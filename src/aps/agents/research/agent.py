"""
aps.agents.research.agent — Research Agent.

EXTRACTED from Open Deep Research, not forked. The control-flow shape (bind tools →
model emits calls → execute → feed back → loop → compress) is ODR's; the code,
types, and tools are yours. ~70 lines you fully own and can defend in a review.

Flow:  PLAN (system prompt frames the task)
       → TOOL LOOP (model ↔ scoped retrieval+analysis tools, capped)
       → COMPRESSION (dedupe_and_rank_evidence + validate_with_sources)
       → typed ResearchReturn

The loop never lets raw tool output pile up in the model's context — the model gets
compact text summaries; structured Evidence is held by the loop and compressed at the
end. That separation IS the Req-3 long-horizon context strategy.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from aps.config.settings import get_chat_model, get_settings
from aps.state.models import Evidence, ResearchReturn
from aps.tools.registry import tools_for
from aps.tools.binding import bind, drain_results
from aps.infra.retry import with_retry
from aps.infra.llm import acquire_llm
from aps.orchestrator.cancel import checkpoint

_SYSTEM = """You are a market-research agent for a startup studio.
Given a product idea, investigate it using the tools available. Find:
- real user pain points (GitHub issues, HN, Reddit, Stack Exchange),
- competitors and their features/pricing,
- signals of market size and demand.

How to search (this matters — vague keyword queries return off-topic noise):
1. Read the idea carefully — what specific market, users, and problem does it name?
2. Write SPECIFIC, intent-bearing queries that describe THIS idea, not one stray keyword
   (for "Private Activity Tracker" search "privacy-focused activity tracking app", not "tracker").
3. Start broad, then narrow as you learn the real vocabulary of the space.
4. Keep only evidence that is actually about this idea — a result that merely shares a word
   (an unrelated "AdBlock" or "Gmail" gripe) is noise; do not pursue it.

Call tools to gather REAL evidence. Prefer specific sources over generic web search
when you can name a repo, subreddit, or package. Stop when you have enough grounded
evidence to characterize the market. Do not write a report — just gather."""

# Floor-guard size: when EVERY gathered item scores below the relevance cutoff, keep this many
# of the best-scoring ones (rather than emitting zero) and mark the brief degraded(low_relevance).
_RELEVANCE_FLOOR_K = 5


def gather_evidence(idea: str, *, focus: str | None = None,
                    provider: str | None = None,
                    seed_queries: list[str] | None = None) -> tuple[list[Evidence], int]:
    """The research tool-loop: bind the scoped tools, let the model select+call them,
    feed compact results back, loop until done or capped.

    Returns ``(evidence, n_tool_calls)`` where ``n_tool_calls`` is the count of actual
    tool invocations executed (not loop iterations). Evidence is captured out-of-band
    so the model only ever sees compact text summaries (Req-3).

    `focus` augments the system prompt so a fan-out unit steers toward a distinct angle
    and source set; the research supervisor passes one focus per parallel sub-researcher.
    `seed_queries` (intent-based query planning) are concrete, idea-anchored search phrases
    appended to the task so the model starts its loop on-topic instead of improvising vague
    keywords; the single-unit path passes `plan_queries(idea)`.
    """
    s = get_settings()
    # Bind ONLY retrieval tools to the model (W2): these are what it should *select*, and
    # their arg schemas are flat (str/int/list[str]) so Gemini's strict function-calling
    # accepts them. The analysis tools run deterministically in _compress() over the
    # evidence the loop already holds — the model never calls them, so their nested
    # list[Evidence] schemas never reach the provider and can't break Gemini tool-calling.
    tools = tools_for("retrieval")
    # `provider` (P10) pins this sub-researcher's preferred provider in multi-provider mode;
    # ignored on the single-provider path. In chain mode the FailoverChatModel throttles each
    # provider's bucket itself, so we DON'T also throttle the generic "llm" bucket here.
    chain_mode = bool((os.environ.get("APS_PROVIDER_CHAIN") or "").strip())
    model = get_chat_model(prefer=provider)
    bound, lc_by_name = bind(model, tools)

    system = _SYSTEM
    task = f"Product idea: {idea}"
    if focus:
        system = (f"{_SYSTEM}\n\nFocus this investigation specifically on: {focus}. "
                  f"Prefer the tools/sources most likely to surface evidence for that angle.")
        task = f"Product idea: {idea}\nResearch focus: {focus}"
    if seed_queries:
        task += ("\nSuggested starting searches (use or refine these on-topic phrases): "
                 + "; ".join(seed_queries))
    messages = [SystemMessage(system), HumanMessage(task)]
    collected: list[Evidence] = []
    n_calls = 0

    # The LLM call is the only unguarded I/O in the loop (retrieval tools already retry
    # transport errors via infra.http). Wrap it so a transient error / 429 backs off and
    # recovers; if it still fails the exception propagates to the supervisor's per-unit guard.
    invoke = with_retry(attempts=3)(bound.invoke)

    for _ in range(s.tool_budget()):                      # recursion cap (TRD C2); depth knob 1.7
        checkpoint()                                      # cooperative cancel (plan 2.2)
        if not chain_mode:
            acquire_llm()                                 # single-provider: throttle here
        ai = invoke(messages)                             # chain mode: failover throttles per provider
        messages.append(ai)
        calls = getattr(ai, "tool_calls", None)
        if not calls:                                     # model is done gathering
            break
        n_calls += len(calls)                            # count each real invocation
        # Scatter-gather (1.1): the model often requests several independent tools in one
        # round; running them back-to-back serializes ~2 s of network each. Execute the
        # round in parallel — the infra they touch is thread-safe (per-host rate limiter,
        # with_retry, GIL-atomic _LAST_RESULTS append), and drain_results() runs below on
        # THIS loop thread after every call has joined. ToolMessages are appended in the
        # model's original call order so the message history stays deterministic.
        by_id = _execute_round(calls, lc_by_name)
        for call in calls:                                # preserve order for the transcript
            messages.append(ToolMessage(content=by_id[call["id"]], tool_call_id=call["id"]))
        for _name, result in drain_results():             # pull structured Evidence
            if result.ok:
                collected.extend(result.evidence)

    return collected, n_calls


def _execute_round(calls: list, lc_by_name: dict) -> dict[str, str]:
    """Run one round of tool calls in parallel, returning {tool_call_id: compact_text}.

    Each call is independent I/O, so concurrency turns the round's cost from the SUM of the
    tool latencies into the MAX. Bounded at 4 workers (the typical round is 1–4 calls); a
    single-call round skips the pool entirely. Per-host rate limiting still serializes calls
    to the same source, so this can't stampede a free-tier quota.
    """
    def _one(call: dict) -> tuple[str, str]:
        name = call.get("name")
        tool = lc_by_name.get(name)
        if tool is None:
            return call["id"], f"[error] unknown tool {name}"
        try:
            # invoking the wrapped tool runs the real tool and captures its structured
            # ToolResult out-of-band (binding._LAST_RESULTS); the model only sees the
            # compact text we return here (Req-3 discipline).
            return call["id"], tool.invoke(call.get("args", {}))
        except Exception as e:
            return call["id"], f"[error] {name}: {e}"

    if len(calls) <= 1:
        return dict(_one(c) for c in calls)
    with ThreadPoolExecutor(max_workers=min(len(calls), 4)) as pool:
        return dict(pool.map(_one, calls))


def run_research(idea: str) -> ResearchReturn:
    """Single-unit research: gather evidence, then compress to a typed brief.

    Backward-compatible entrypoint — `scripts/run_research.py` and the single-unit path
    call this directly. The fan-out supervisor (research/supervisor.py) reuses
    `gather_evidence` per sub-topic and compresses over the union instead.
    """
    seeds: list[str] | None = None
    if get_settings().enable_query_planning:
        from aps.agents.research.supervisor import plan_queries  # lazy: avoid agent↔supervisor cycle
        seeds = plan_queries(idea)
    evidence, n_calls = gather_evidence(idea, seed_queries=seeds)
    result = _compress(idea, evidence)
    result.tool_calls = n_calls
    return result


def _compress(idea: str, evidence: list[Evidence]) -> ResearchReturn:
    """COMPRESSION node — your replacement for ODR's report writer + dedup.

    Calls your own analysis tools so the logic stays in tools, not buried here.
    """
    from aps.tools.analysis import dedupe_and_rank_evidence as dd
    from aps.tools.analysis import validate_with_sources as vs
    from aps.tools.analysis import extract_pain_points as pp
    from aps.tools.analysis import estimate_market_size as ms
    from aps.tools.analysis import build_competitor_matrix as cm

    # Drop fixture-fallback evidence: tools that failed (no key/network) return labeled
    # placeholder data, which must not ground a real brief (it's what let resume/ATS fixtures
    # bleed into unrelated ideas). If nothing real remains, the caller degrades honestly.
    evidence = [e for e in evidence if not (getattr(e, "title", "") or "").startswith("[fixture]")]

    # RELEVANCE GATE (intent filter) — score every item against the idea, then gate the PAIN
    # extraction input to the relevant subset. Pains→features were the garbage: a keyword-
    # coincidence gripe ("YouTube AdBlock is missing" for a privacy tracker) is a syntactically
    # valid complaint, so the noise filter passes it — only an idea-relevance check stops it.
    # Competitor/market extraction keep the FULL set: they have their own gates (a competitor
    # denylist; a TAM money/floor), and a real competitor can be on-topic while sharing few of
    # the idea's exact words ("SAST scanning" vs "security review") — lexical overlap would wrongly
    # drop it. Runs at the single chokepoint every path shares (loop, fan-out, keyless).
    s = get_settings()
    degraded = False
    degrade_reason: str | None = None
    mean_rel = 0.0

    ranked = dd.TOOL.run(evidence=[e.model_dump() for e in evidence]).payload or evidence
    valid = vs.TOOL.run(evidence=ranked).payload or ranked

    pain_input = valid
    if s.enable_relevance_gate and valid and isinstance(valid[0], Evidence):
        from aps.tools.analysis import score_evidence_relevance as sr
        from aps.agents.research import _relevance as rel
        prof = sr.idea_profile(idea)
        for e in valid:
            e.relevance = sr.relevance_score(prof, e)
        mean_rel = round(sum((e.relevance or 0.0) for e in valid) / max(len(valid), 1), 3)
        relevant = [e for e in valid if (e.relevance or 0.0) >= s.relevance_min]
        relevant = rel.judge(idea, valid, relevant, s, min_score=s.relevance_min)
        if relevant:
            pain_input = relevant
        else:                              # nothing on-topic → pains would be all noise; degrade
            pain_input = sorted(valid, key=lambda e: e.relevance or 0.0, reverse=True)[:_RELEVANCE_FLOOR_K]
            degraded, degrade_reason = True, "low_relevance"

    pains = pp.TOOL.run(evidence=pain_input).payload or []
    size = ms.TOOL.run(evidence=valid).payload or ""
    comps = cm.TOOL.run(evidence=valid).payload or []

    # tolerate stubbed analysis tools during early build: fall back to raw evidence
    return ResearchReturn(
        idea=idea,
        market_size=size if isinstance(size, str) else "",
        competitors=comps if isinstance(comps, list) else [],
        pain_points=pains if isinstance(pains, list) else [],
        evidence=valid if isinstance(valid, list) and valid and isinstance(valid[0], Evidence) else evidence,
        degraded=degraded,
        degrade_reason=degrade_reason,
        evidence_relevance=mean_rel,
    )
