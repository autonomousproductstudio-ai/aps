"""T2.4 — GitHub Launch Mode: deterministic plan, safe preview, REAL API path (mocked HTTP).

The live calls are exercised through a fake `infra.http` so the real code path is tested
without touching GitHub. With a real PAT the same path creates an actual repo (see
scripts/live_github_launch_smoke.py).
"""
from __future__ import annotations

from aps.state.models import PRD, ExecutionPlan, Feature, PitchPackage
from aps.launch import build_launch_plan, launch_github
import aps.infra.http as http


def _prd():
    return PRD(idea="Build an AI SaaS for resume screening",
              features=[Feature(title="Reliable PDF parsing", description="handle pdfs", priority="Must")],
              mvp_scope="Parse reliably.", requirements=["[Must] parse"])


def _execution():
    return ExecutionPlan(
        backlog=[{"id": "APS-001", "title": "Parse PDFs", "type": "story", "priority": "Must", "points": 5},
                 {"id": "APS-002", "title": "Auth", "type": "task", "priority": "Must", "points": 3}],
        sprints=[{"sprint": 1, "items": [{"id": "APS-001", "title": "Parse PDFs"}], "points": 5}],
        roadmap="MVP", infra_cost="$200/mo")


def test_build_launch_plan_is_deterministic_and_grounded():
    plan = build_launch_plan(_prd().idea, _prd(), _execution(), PitchPackage(pitch_outline="1. Problem"))
    assert plan.repo_name == "build-an-ai-saas-for-resume-screening"
    assert len(plan.issues) == 2 and plan.issues[0].title == "Parse PDFs"
    assert plan.milestones == ["Sprint 1"]
    assert plan.issues[0].sprint == 1            # mapped to its sprint
    assert "Reliable PDF parsing" in plan.readme and "# Build an AI SaaS" in plan.readme
    # determinism
    assert build_launch_plan(_prd().idea, _prd(), _execution()).model_dump() == \
        build_launch_plan(_prd().idea, _prd(), _execution()).model_dump()


def test_preview_without_token_makes_no_network(monkeypatch):
    monkeypatch.delenv("APS_GITHUB_PAT", raising=False)
    # blow up if any HTTP is attempted
    monkeypatch.setattr(http, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network!")))
    plan = build_launch_plan(_prd().idea, _prd(), _execution())
    res = launch_github(plan)
    assert res.created is False and res.dry_run is True
    assert "Preview" in res.message and res.full_name.endswith(plan.repo_name)


class _Resp:
    def __init__(self, payload, status=201):
        self._p = payload
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):
        return self._p


def test_real_launch_path_with_mocked_github(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(("POST", url))
        if url.endswith("/user/repos"):
            return _Resp({"full_name": "me/build-an-ai-saas-for-resume-screening",
                          "html_url": "https://github.com/me/build-an-ai-saas-for-resume-screening"})
        if url.endswith("/milestones"):
            return _Resp({"number": 1})
        if url.endswith("/issues"):
            return _Resp({"html_url": "https://github.com/me/x/issues/1", "number": 1})
        return _Resp({}, 404)

    def fake_request(method, url, **kw):
        calls.append((method, url))
        return _Resp({}, 201)   # README PUT

    monkeypatch.setattr(http, "post", fake_post)
    monkeypatch.setattr(http, "request", fake_request)

    plan = build_launch_plan(_prd().idea, _prd(), _execution())
    res = launch_github(plan, token="ghp_fake")

    assert res.created is True and res.dry_run is False
    assert res.repo_url.startswith("https://github.com/")
    assert res.full_name == "me/build-an-ai-saas-for-resume-screening"
    assert len(res.issue_urls) == 2 and res.milestones_created == 1
    # the real sequence happened: create repo → PUT README → milestone → issues
    assert ("POST", "https://api.github.com/user/repos") in calls
    assert any(m == "PUT" for m, _ in calls)
    assert sum(1 for m, u in calls if u.endswith("/issues")) == 2


def test_launch_failure_is_reported_not_raised(monkeypatch):
    def boom(url, **kw):
        return _Resp({}, 500)
    monkeypatch.setattr(http, "post", boom)
    res = launch_github(build_launch_plan(_prd().idea, _prd(), _execution()), token="ghp_fake")
    assert res.created is False and "failed" in res.message.lower()


def test_permission_denied_gives_actionable_message(monkeypatch):
    # the real live failure: a fine-grained PAT without Administration can't create repos (403).
    def forbidden(url, **kw):
        return _Resp({"message": "Resource not accessible by personal access token"}, 403)
    monkeypatch.setattr(http, "post", forbidden)
    res = launch_github(build_launch_plan(_prd().idea, _prd(), _execution()), token="github_pat_x")
    assert res.created is False
    low = res.message.lower()
    assert "403" in res.message and "repo" in low
    assert "classic" in low or "administration" in low      # tells the user how to fix it


def test_repo_name_conflict_gives_422_message(monkeypatch):
    def conflict(url, **kw):
        return _Resp({"message": "name already exists on this account"}, 422)
    monkeypatch.setattr(http, "post", conflict)
    res = launch_github(build_launch_plan(_prd().idea, _prd(), _execution()), token="ghp_fake")
    assert res.created is False and "422" in res.message
