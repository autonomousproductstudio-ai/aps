"""Retrieval tools: structural checks over all 20 + offline fixture-path for key-gated ones.

We do NOT make live calls here. Tools that need a key (github, web_search) take the
fixture-fallback path with no key set; no-key tools are checked structurally only, so the
suite stays offline and deterministic.
"""
from __future__ import annotations

import pytest

from aps.tools.registry import tools_for
from aps.state.models import ToolResult, Evidence

RETRIEVAL = tools_for("retrieval")


@pytest.mark.parametrize("tool", RETRIEVAL, ids=[t.name for t in RETRIEVAL])
def test_retrieval_tool_shape(tool):
    assert tool.namespace == "retrieval"
    fields = tool.args_schema.model_fields
    assert fields, f"{tool.name}: must declare typed args"


def test_github_issues_fixture_path(monkeypatch):
    from aps.tools.retrieval import github_issues as gi
    monkeypatch.delenv("APS_GITHUB_PAT", raising=False)
    out = gi.TOOL.run(repo="langchain-ai/langgraph")
    assert isinstance(out, ToolResult)
    assert out.ok and out.evidence
    assert all(isinstance(e, Evidence) for e in out.evidence)
    assert out.evidence[0].source == "github"


def test_web_search_fixture_path(monkeypatch):
    from aps.tools.retrieval import web_search as ws
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    out = ws.TOOL.run(query="resume screening market size")
    assert isinstance(out, ToolResult)
    assert out.ok and out.evidence
    assert out.evidence[0].url.startswith("http")


def test_bad_args_return_typed_error_not_crash():
    from aps.tools.retrieval import github_issues as gi
    # missing required `repo` -> BaseTool turns the ValidationError into ok=False
    out = gi.TOOL.run()
    assert isinstance(out, ToolResult)
    assert out.ok is False and out.error and out.error.startswith("bad_args")
