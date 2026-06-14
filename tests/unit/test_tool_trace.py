"""Per-tool event sink (plan §4): tools emit tool_call/tool_result with timing through the
run's sink, and are silent (no-op) outside a run."""
from __future__ import annotations

from aps.infra import trace
from aps.tools.analysis import dedupe_and_rank_evidence as dd


def test_tool_emits_call_and_result_through_sink():
    events: list[tuple[str, dict]] = []
    tok = trace.set_sink(lambda t, d: events.append((t, d)))
    try:
        dd.TOOL.run(evidence=[])
    finally:
        trace.reset(tok)
    types = [t for t, _ in events]
    assert types == ["tool_call", "tool_result"]
    result = events[1][1]
    assert result["tool"] == dd.TOOL.name
    assert "ms" in result and result["ms"] >= 0
    assert result["ok"] is True


def test_emit_is_noop_without_a_sink():
    # No sink installed → running a tool must not raise (CLI / bare-call path).
    out = dd.TOOL.run(evidence=[])
    assert out.ok is True
