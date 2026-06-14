"""Deterministic keyless research — real evidence with zero credentials (Phase C).

The LLM tool-loop needs a model to *select* tools, but several retrieval tools need no API
key at all. When there's no LLM key, instead of falling back to the labeled stub we call a
fixed set of no-key tools directly on the idea and compress their real output into a typed
`ResearchReturn`. That turns the worst failure mode (an incoherent stub package) into a
genuine — if simpler — grounded result any judge can reproduce with no credentials.

No LLM, deterministic. Each tool's args is just `query=<idea>`; sources that need exact
identifiers (PyPI/npm package names) are intentionally excluded.
"""
from __future__ import annotations

import importlib

from aps.state.models import Evidence, ResearchReturn
from aps.agents.research.agent import _compress

# No-key, free-text-query retrieval tools (each returns real data without any credential).
# (module path, extra kwargs) — `query=<idea>` is always passed.
_KEYLESS_TOOLS = (
    ("aps.tools.retrieval.hn_search", {"limit": 10}),
    ("aps.tools.retrieval.stackexchange_search", {"limit": 10}),
    ("aps.tools.retrieval.wikipedia_summary", {"limit": 3}),
    ("aps.tools.retrieval.arxiv_search", {"limit": 6}),
    ("aps.tools.retrieval.jobs_search", {"limit": 10}),
)


# How many planned phrases the keyless path issues per tool (bounded so N_tools × N_phrases stays
# small on the free/no-key path; the relevance gate + dedupe clean the merged union).
_KEYLESS_QUERY_K = 3


def _keyless_queries(idea: str) -> list[str]:
    """Idea-anchored search phrases for the no-key path. With no model, `plan_queries` falls back
    to its deterministic generator, so the keyless tools are asked several on-topic questions
    instead of one bare token-query. Honors APS_ENABLE_QUERY_PLANNING (off ⇒ the prior single
    token-query). Falls back to the raw idea if anything goes wrong."""
    try:
        from aps.config.settings import get_settings
        if not get_settings().enable_query_planning:
            from aps.tools.analysis._text import tokenize
            terms = tokenize(idea)
            return [" ".join(terms) if terms else idea]
        from aps.agents.research.supervisor import plan_queries
        return plan_queries(idea, n=_KEYLESS_QUERY_K)[:_KEYLESS_QUERY_K] or [idea]
    except Exception:
        return [idea]


def keyless_research(idea: str) -> ResearchReturn:
    """Run the no-key retrieval tools directly on the planned `idea` queries and compress.

    Returns real (deterministic) evidence — `degraded` stays False; this is a genuine result,
    not the stub. Each no-key tool is asked the top-K idea-anchored phrases; a per-tool/per-query
    failure is skipped so one flaky source can't sink the run. The relevance gate in `_compress`
    then drops anything still off-topic, and dedupe collapses cross-query duplicates.
    """
    queries = _keyless_queries(idea)
    collected: list[Evidence] = []
    for mod_path, extra in _KEYLESS_TOOLS:
        try:
            tool = importlib.import_module(mod_path).TOOL
        except Exception:
            continue
        for query in queries:
            try:
                res = tool.run(query=query, **extra)
                if res.ok:
                    collected.extend(res.evidence)
            except Exception:
                continue
    return _compress(idea, collected)
