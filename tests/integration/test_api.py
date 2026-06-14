"""FastAPI surface wired to the orchestrator (API_CONTRACT.md), via Starlette TestClient.

The run executes in a background thread; we poll GET /runs/{id} until it completes, then
assert the artifact + event endpoints. No LLM key needed (research degrades to the stub).
"""
from __future__ import annotations

import time

import pytest
from starlette.testclient import TestClient

from aps.api.main import app
from aps.config.settings import get_settings

KEY = get_settings().api_key
HDR = {"X-APS-Key": KEY}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _wait_complete(client, run_id, tries=100):
    for _ in range(tries):
        r = client.get(f"/runs/{run_id}", headers=HDR)
        if r.json().get("status") in ("complete", "degraded", "failed"):
            return r.json()
        time.sleep(0.05)
    raise AssertionError("run did not finish in time")


def test_auth_required():
    with TestClient(app) as c:
        assert c.post("/runs", json={"idea": "x"}).status_code == 401
        assert c.get("/runs/nope").status_code == 401


def test_full_run_via_api(client):
    r = client.post("/runs", json={"idea": "Build an AI SaaS for resume screening"},
                    headers=HDR)
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    # admission-control queue (2.1): submit_run returns "queued"; a worker thread may have
    # already flipped it to "running" — both are valid immediately after submission (the race
    # that made this assert flaky when it demanded "running"). The terminal state is checked below.
    assert r.json()["status"] in ("queued", "running")

    done = _wait_complete(client, run_id)
    # No LLM key in CI -> honest "degraded" (ran on fixture), still all five artifacts.
    assert done["status"] == "degraded"
    assert set(done["artifacts"]) >= {"research", "prd", "trd", "execution", "pitch"}

    # artifact endpoint returns a real PRD
    prd = client.get(f"/runs/{run_id}/artifacts/prd", headers=HDR)
    assert prd.status_code == 200
    assert prd.json()["idea"] == "Build an AI SaaS for resume screening"
    assert prd.json()["features"]

    # OpenAPI carried in the TRD artifact
    trd = client.get(f"/runs/{run_id}/artifacts/trd", headers=HDR)
    assert trd.status_code == 200
    assert trd.json()["api_spec"]["openapi"].startswith("3.")

    # W6: ?format=md returns Markdown; the plain JSON path is unchanged
    md = client.get(f"/runs/{run_id}/artifacts/prd?format=md", headers=HDR)
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert "# Product Requirements Document" in md.text
    assert "Build an AI SaaS for resume screening" in md.text
    # default (no format) is still JSON
    assert client.get(f"/runs/{run_id}/artifacts/prd", headers=HDR).json()["idea"]

    # Startup Score (T1.4): derived endpoint, JSON + Markdown
    sc = client.get(f"/runs/{run_id}/score", headers=HDR)
    assert sc.status_code == 200
    body = sc.json()
    assert 0 <= body["overall"] <= 10 and body["verdict"] and len(body["dimensions"]) == 5
    scmd = client.get(f"/runs/{run_id}/score?format=md", headers=HDR)
    assert scmd.status_code == 200 and scmd.headers["content-type"].startswith("text/markdown")
    assert "Startup Score" in scmd.text

    # Architecture Mermaid (T2.2): TRD only
    mm = client.get(f"/runs/{run_id}/artifacts/trd?format=mermaid", headers=HDR)
    assert mm.status_code == 200 and mm.headers["content-type"].startswith("text/markdown")
    assert "```mermaid" in mm.text and "flowchart TD" in mm.text
    # mermaid is not offered for non-trd artifacts
    assert client.get(f"/runs/{run_id}/artifacts/prd?format=mermaid", headers=HDR).status_code == 404

    # Autonomous Debate (T2.3): verdict + both sides, JSON + Markdown
    db = client.get(f"/runs/{run_id}/debate", headers=HDR)
    assert db.status_code == 200
    dbody = db.json()
    assert dbody["verdict"] and dbody["build_case"] and dbody["risk_case"]
    dbmd = client.get(f"/runs/{run_id}/debate?format=md", headers=HDR)
    assert dbmd.status_code == 200 and "Verdict" in dbmd.text

    # GitHub Launch Mode (T2.4): dry-run preview creates nothing, returns the plan
    lr = client.post(f"/runs/{run_id}/launch/github", json={"dry_run": True}, headers=HDR)
    assert lr.status_code == 200
    lbody = lr.json()
    assert lbody["dry_run"] is True and lbody["created"] is False
    assert "Preview" in lbody["message"]

    # Explain-Why (T2.5): per-feature provenance, JSON + Markdown
    ex = client.get(f"/runs/{run_id}/explain", headers=HDR)
    assert ex.status_code == 200
    ebody = ex.json()
    assert 0 <= ebody["overall_confidence"] <= 1 and isinstance(ebody["features"], list)
    exmd = client.get(f"/runs/{run_id}/explain?format=md", headers=HDR)
    assert exmd.status_code == 200 and "Explain-Why" in exmd.text


def test_unknown_artifact_and_run(client):
    assert client.get("/runs/does_not_exist", headers=HDR).status_code == 404
    r = client.post("/runs", json={"idea": "x"}, headers=HDR)
    rid = r.json()["run_id"]
    _wait_complete(client, rid)
    assert client.get(f"/runs/{rid}/artifacts/bogus", headers=HDR).status_code == 404


def test_event_stream(client):
    rid = client.post("/runs", json={"idea": "A privacy-first habit tracker"},
                      headers=HDR).json()["run_id"]
    _wait_complete(client, rid)
    body = client.get(f"/runs/{rid}/events").text
    assert "event: run_start" in body
    assert "event: run_complete" in body
    assert "event: agent_start" in body
