"""
aps.tools.binding — the ONE bridge between your Tool protocol and LangChain.

This is the only piece of "ODR magic" you actually need: the model can only emit
tool calls for tools it has been *bound* to. ODR binds its search tools; you bind
your registry tools the same way. Everything downstream (the loop, compression) is
your own code over your own ToolResult.

Read once from ODR: how it constructs LangChain tools and calls model.bind_tools(...).
Then this file replaces all of it for your design.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from aps.tools.base import ToolImpl
from aps.state.models import ToolResult


def _wrap(tool: ToolImpl) -> StructuredTool:
    """Adapt one of YOUR tools into a LangChain StructuredTool the model can call.

    The model reads `description` + `args_schema` to decide. We return the tool's
    ToolResult serialized so it can be appended to the message history; the real
    structured ToolResult is captured out-of-band by the loop via `_LAST_RESULTS`.
    """
    def _run(**kwargs: Any) -> str:
        result: ToolResult = tool.run(**kwargs)
        _LAST_RESULTS.append((tool.name, result))
        # what the MODEL sees back: compact text. The structured evidence is kept
        # by the loop, not crammed into the model's context (Req-3 discipline).
        if not result.ok:
            return f"[{tool.name}] error: {result.error}"
        n = len(result.evidence)
        head = "; ".join(e.title or e.snippet[:60] for e in result.evidence[:3])
        return f"[{tool.name}] {n} evidence item(s). top: {head}"

    return StructuredTool.from_function(
        func=_run,
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
    )


# The loop reads structured results from here after each model turn, then clears it.
_LAST_RESULTS: list[tuple[str, ToolResult]] = []


def bind(model, tools: list[ToolImpl]):
    """Return (bound_model, lc_tools_by_name). `bound_model` emits tool calls."""
    lc_tools = [_wrap(t) for t in tools]
    bound = model.bind_tools(lc_tools)
    return bound, {t.name: t for t in lc_tools}


def drain_results() -> list[tuple[str, ToolResult]]:
    """Pop the structured ToolResults captured since the last drain."""
    out = list(_LAST_RESULTS)
    _LAST_RESULTS.clear()
    return out
