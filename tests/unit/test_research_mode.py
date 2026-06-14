"""Research depth knob (plan 1.7): fast vs deep scaling of fan-out + tool budget."""
from __future__ import annotations

from aps.config.settings import Settings


def test_fast_mode_uses_base_limits():
    s = Settings(research_mode="fast")
    assert s.research_units() == s.max_concurrent_researchers
    assert s.tool_budget() == s.max_tool_calls_per_agent


def test_deep_mode_widens_fanout_and_budget():
    s = Settings(research_mode="deep")
    assert s.research_units() == s.deep_concurrent_researchers
    assert s.tool_budget() == s.deep_tool_calls_per_agent
    assert s.research_units() > s.max_concurrent_researchers
    assert s.tool_budget() > s.max_tool_calls_per_agent


def test_default_is_fast():
    assert Settings().research_mode == "fast"
