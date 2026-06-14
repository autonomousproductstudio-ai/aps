"""W4 — token-gated tools degrade loudly: fixture evidence is [fixture]-stamped + logged."""
from __future__ import annotations

import aps.tools.base as base
from aps.state.models import Evidence


def test_fixture_fallback_stamps_and_logs(monkeypatch):
    class _FakeLog:
        def __init__(self):
            self.warnings = []
        def warning(self, *a, **k):
            self.warnings.append((a, k))
        def debug(self, *a, **k):
            pass

    fake = _FakeLog()
    monkeypatch.setattr(base, "_LOG", fake)

    res = base.fixture_or_error(
        "TAVILY_API_KEY not set",
        evidence=[Evidence(source="web", url="https://x.com/a", title="Live title", snippet="s")],
    )
    assert res.ok
    assert res.evidence[0].title.startswith("[fixture]")          # judge can see it's fixture
    assert fake.warnings and fake.warnings[0][0][0] == "tool_fixture_fallback"  # and it's logged


def test_token_gated_tool_returns_stamped_fixture(monkeypatch):
    # web_search with no key takes the fixture path with NO network call
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from aps.tools.retrieval import web_search as ws
    out = ws.TOOL.run(query="resume screening market")
    assert out.ok and out.evidence
    assert all(e.title.startswith("[fixture]") for e in out.evidence)


def test_no_fallback_when_disabled(monkeypatch):
    from aps.config.settings import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("APS_ALLOW_FIXTURE_FALLBACK", "false")
    try:
        res = base.fixture_or_error("boom", evidence=[])
        assert res.ok is False and res.error == "boom"
    finally:
        get_settings.cache_clear()
