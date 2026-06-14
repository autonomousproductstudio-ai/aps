"""W2 — research tool-loop: Gemini-safe binding, real tool execution, key-gated live check.

Offline and hermetic: a fake model scripts tool calls; key-gated tools take their fixture
path (no network). The live test is skipped unless an LLM key is present.
"""
from __future__ import annotations

import os

import pytest
from langchain_core.messages import AIMessage

import aps.agents.research.agent as R
from aps.tools.registry import tools_for

# JSON-schema primitive types Gemini's function-calling reliably accepts.
_SIMPLE = {"string", "integer", "number", "boolean", "null"}


def _is_gemini_safe(schema: dict) -> bool:
    """A tool arg schema is Gemini-safe if it's flat: no nested model ($defs/$ref) and
    every property is a primitive or an array of primitives (optionally wrapped in anyOf)."""
    if "$defs" in schema or "$ref" in str(schema):
        return False
    for prop in schema.get("properties", {}).values():
        t = prop.get("type")
        if t == "array":
            if (prop.get("items") or {}).get("type") not in _SIMPLE:
                return False
        elif t in _SIMPLE:
            continue
        elif "anyOf" in prop:  # Optional[...] -> anyOf of simple types
            if not all(o.get("type") in _SIMPLE or o.get("type") == "array"
                       for o in prop["anyOf"]):
                return False
        else:
            return False
    return True


@pytest.mark.parametrize("tool", tools_for("retrieval"),
                         ids=[t.name for t in tools_for("retrieval")])
def test_retrieval_tool_schemas_are_gemini_safe(tool):
    # the model only ever SELECTS retrieval tools, so these must be Gemini-compatible
    assert _is_gemini_safe(tool.args_schema.model_json_schema()), tool.name


def test_analysis_tools_are_not_model_bound():
    # analysis tools carry nested list[Evidence] schemas (not Gemini-safe) — which is exactly
    # why the research loop binds retrieval ONLY and runs analysis in _compress (W2).
    from aps.tools.analysis import extract_pain_points as pp
    assert not _is_gemini_safe(pp.TOOL.args_schema.model_json_schema())


class _FakeBound:
    def __init__(self, scripts):
        self.scripts = scripts
        self.i = 0

    def invoke(self, messages):
        msg = self.scripts[min(self.i, len(self.scripts) - 1)]
        self.i += 1
        return msg


class _FakeModel:
    def __init__(self, scripts):
        self.scripts = scripts

    def bind_tools(self, lc_tools):
        return _FakeBound(self.scripts)


def test_loop_executes_selected_tools_and_collects_evidence(monkeypatch):
    # no keys -> github/web take their fixture path (no network); fully hermetic
    monkeypatch.delenv("APS_GITHUB_PAT", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(R, "acquire_llm", lambda *a, **k: 0.0)
    scripts = [
        AIMessage(content="", tool_calls=[
            {"name": "github_list_issues", "args": {"repo": "x/y"}, "id": "c1"},
            {"name": "web_search", "args": {"query": "demand"}, "id": "c2"},
        ]),
        AIMessage(content="done", tool_calls=[]),
    ]
    monkeypatch.setattr(R, "get_chat_model", lambda *a, **k: _FakeModel(scripts))
    ev, n_calls = R.gather_evidence("a privacy-first habit tracker")
    assert ev, "loop must collect evidence from the tools the model selected"
    assert {e.source for e in ev}  # real Evidence objects with sources
    assert n_calls >= 1            # tool-call counter reflects the tools the model selected


@pytest.mark.live
@pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("NVIDIA_API_KEY")),
    reason="no LLM key — live tool-selection check (W2) requires GEMINI_API_KEY or NVIDIA_API_KEY",
)
def test_live_research_selects_tools_and_gathers_evidence():
    ev, _ = R.gather_evidence("a privacy-first habit tracker app")
    assert ev, "live model must select tools and gather real evidence"
