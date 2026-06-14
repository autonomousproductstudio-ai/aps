"""Shared helpers for the deterministic downstream agents (P2).

The downstream agents (Product/Architecture/Execution/Presentation) are deterministic
tool *pipelines*, not LLM tool-loops — see decision.md D2. They still honor per-agent
tool scoping (ADR-0005): each agent pulls only `tools_for(namespace)` from the registry
and dispatches by tool name through `call()`, which also records metrics.

Leading underscore → the registry/tooling never mistakes this for a tool module.
"""
from __future__ import annotations

from aps.tools.registry import tools_for
from aps.state.models import ToolResult


def scoped(namespace: str) -> dict[str, object]:
    """Return {tool_name: tool} for exactly the tools this agent is allowed to see."""
    return {t.name: t for t in tools_for(namespace)}


def call(tools: dict[str, object], tool_name: str, **kwargs):
    """Run a scoped tool by name, record the call, and return its payload.

    `tool_name` is positional so a tool may freely have an argument literally called `name`
    (e.g. the brand tools) without colliding with this helper's signature.

    Raises KeyError if the agent reaches for a tool outside its scope (a real guardrail),
    and ValueError if the tool reports failure — surfacing problems instead of emitting a
    silently-broken artifact.
    """
    tool = tools[tool_name]  # KeyError = out-of-scope tool, intentionally loud
    result: ToolResult = tool.run(**kwargs)  # tool.run() records metrics centrally
    if not result.ok:
        raise ValueError(f"tool {tool_name} failed: {result.error}")
    return result.payload
