"""Reference unit test. Runs against fixture fallback — no live call in CI (EVALUATION §6)."""
from aps.tools.retrieval.github_issues import TOOL


def test_returns_valid_toolresult_via_fixture(monkeypatch):
    monkeypatch.delenv("APS_GITHUB_PAT", raising=False)  # force fixture path
    monkeypatch.setenv("APS_ALLOW_FIXTURE_FALLBACK", "true")
    res = TOOL.run(repo="example/repo")
    assert res.ok
    assert res.evidence and res.evidence[0].source == "github"


def test_bad_args_rejected():
    res = TOOL.run(repo="x", limit=999)   # limit>50 -> schema rejects
    assert not res.ok and "bad_args" in (res.error or "")
