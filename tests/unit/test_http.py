"""infra.http: rate-limit + retry + logging wrapper, and retrieval tools routed through it.

No real network: we monkeypatch `requests.request` / `http.get` with fakes. This also
gives the retrieval tools their first *live-path* coverage (previously only the fixture
fallback was tested)."""
from __future__ import annotations

import pytest

from aps.infra import http
from aps.state.models import ToolResult, Evidence


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = "ok"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_request_retries_transient_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_request(method, url, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise http.requests.exceptions.ConnectionError("boom")
        return _Resp({"ok": True})

    monkeypatch.setattr(http.requests, "request", fake_request)
    r = http.get("https://api.example.com/x", attempts=3)
    assert r.json() == {"ok": True}
    assert calls["n"] == 3  # retried twice, succeeded on the third


def test_request_gives_up_after_attempts(monkeypatch):
    def always_fail(method, url, **kw):
        raise http.requests.exceptions.Timeout("slow")

    monkeypatch.setattr(http.requests, "request", always_fail)
    with pytest.raises(http.requests.exceptions.Timeout):
        http.get("https://api.example.com/x", attempts=2)


def test_get_and_post_delegate_with_method(monkeypatch):
    seen = {}

    def fake_request(method, url, **kw):
        seen["method"] = method
        return _Resp({})

    monkeypatch.setattr(http.requests, "request", fake_request)
    http.get("https://h/x")
    assert seen["method"] == "GET"
    http.post("https://h/x")
    assert seen["method"] == "POST"


def test_host_is_derived_for_rate_key():
    assert http._host("https://api.github.com/repos/x") == "api.github.com"
    assert http._host("not a url") == "unknown"


def test_github_issues_live_path_through_http(monkeypatch):
    """With a token set, the tool takes the live branch and parses a faked response."""
    from aps.tools.retrieval import github_issues as gi
    monkeypatch.setenv("APS_GITHUB_PAT", "fake-token")

    issues = [
        {"html_url": "https://github.com/x/y/issues/1", "title": "Crash on PDF",
         "body": "parser dies"},
        {"html_url": "https://github.com/x/y/pull/2", "title": "a PR",
         "pull_request": {}, "body": "ignore me"},
    ]
    monkeypatch.setattr(http, "get", lambda *a, **k: _Resp(issues))

    out = gi.TOOL.run(repo="x/y")
    assert isinstance(out, ToolResult) and out.ok
    # the PR entry is filtered out; only the real issue becomes evidence
    assert len(out.evidence) == 1
    assert isinstance(out.evidence[0], Evidence)
    assert out.evidence[0].title == "Crash on PDF"


def test_tool_call_is_metered(monkeypatch):
    """BaseTool.run records every call centrally (no-op shim or real prometheus)."""
    import aps.tools.base as base
    seen = []
    monkeypatch.setattr(base, "record_tool_call",
                        lambda name, ns, ok: seen.append((name, ns, ok)))
    from aps.tools.analysis import sentiment_breakdown as sb
    sb.TOOL.run(evidence=[])
    assert seen and seen[-1][0] == "sentiment_breakdown" and seen[-1][1] == "analysis"
