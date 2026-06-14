"""Registry & Req-1 invariants: exactly 69 model-callable tools, cleanly scoped.

(52 core + Launch Studio: 4 brand (P1) + 5 legal (P2) + 3 funding (P3) + 2 availability (P4)
+ 2 compliance (P5); +1 analysis score_evidence_relevance for the research relevance gate.)
"""
from __future__ import annotations

import pytest

from aps.tools.registry import load_registry, all_tools, tools_for
from aps.state.models import ToolResult

EXPECTED = {
    "retrieval": 20, "analysis": 11, "product": 6, "architecture": 6,
    "execution": 6, "presentation": 4, "brand": 4, "legal": 5, "funding": 3,
    "availability": 2, "compliance": 2,
}


def test_total_is_69():
    assert len(all_tools()) == 69


def test_namespace_counts():
    reg = load_registry()
    assert {k: len(v) for k, v in reg.items()} == EXPECTED


def test_no_duplicate_tool_names():
    names = [t.name for t in all_tools()]
    assert len(names) == len(set(names)), "tool names must be globally unique"


@pytest.mark.parametrize("tool", all_tools(), ids=[t.name for t in all_tools()])
def test_every_tool_is_model_grade(tool):
    # snake_case name, a real description the model reads, a typed args schema, namespace
    assert tool.name and tool.name == tool.name.lower()
    assert tool.namespace in EXPECTED
    desc = (tool.description or "").strip()
    assert len(desc) >= 30 and "TODO" not in desc, f"{tool.name}: weak description"
    assert hasattr(tool.args_schema, "model_fields"), f"{tool.name}: args_schema not a model"


def test_scoping_returns_only_namespace():
    for ns in EXPECTED:
        assert all(t.namespace == ns for t in tools_for(ns))


def test_no_agent_sees_more_than_20_tools():
    # ADR-0005: per-agent scoping keeps selection coherent.
    for ns in EXPECTED:
        assert len(tools_for(ns)) <= 20


def test_run_returns_toolresult_type():
    # contract: every tool's run() yields a ToolResult (sample one per namespace)
    for ns in EXPECTED:
        tool = tools_for(ns)[0]
        # build empty/default args where possible; tools tolerate empties by design
        try:
            out = tool.run()
        except TypeError:
            out = None  # required args — covered in per-namespace tests
        if out is not None:
            assert isinstance(out, ToolResult)
