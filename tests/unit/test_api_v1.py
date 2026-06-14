"""The /v1 Frontend Data Contract (docs/backenddatacontract.md) — envelope, auth, every
endpoint's required keys present (§0.8), deterministic mocks, and the websocket stream.

Hermetic: starts no real orchestrator run for the data-shape tests — it injects a fully-formed
StudioState straight into the shared engine's in-memory store and aliases it, so the mappers
run against realistic data with zero network. One test does start a real run to prove the
POST→dashboard path (the orchestrator degrades to the deterministic stub without keys).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aps.api.main import app
from aps.api import main as main_mod
from aps.api.v1 import idmap
from aps.state.models import (
    StudioState, RunStatus, ResearchReturn, PRD, TRD, ExecutionPlan, PitchPackage,
    Competitor, PainPoint, Persona, Feature, Evidence, Severity,
)

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def token() -> str:
    r = client.post("/v1/auth/login", json={"email": "operator@aps.io", "password": "demo1234"})
    assert r.status_code == 200
    return r.json()["data"]["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_state() -> str:
    """Inject a complete StudioState into the engine and return its RUN_ alias (no network)."""
    ev = [Evidence(source="github", url="https://g/1", title="ATS drops PDFs",
                   snippet="The parser keeps dropping valid resumes"),
          Evidence(source="reddit", url="https://r/2", title="cant find tracker",
                   snippet="I can't find a privacy-respecting habit tracker")]
    research = ResearchReturn(
        idea="privacy habit tracker", market_size="$8.4B",
        competitors=[Competitor(name="Habitica", features=["streaks", "reminders"]),
                     Competitor(name="Streaks", features=["reminders"])],
        pain_points=[PainPoint(text="Can't find a privacy-respecting tracker",
                               severity=Severity.HIGH, source_evidence=ev)],
        evidence=ev, tool_calls=12)
    prd = PRD(idea="privacy habit tracker",
              personas=[Persona(name="Sam", role="user", goals=["track offline"])],
              features=[Feature(title="Offline Sync", description="x", priority="Must")],
              sources=ev)
    trd = TRD(stack=["FastAPI", "React"], api_spec={"openapi": "3.0.3"})
    state = StudioState(idea="privacy habit tracker", status=RunStatus.COMPLETE,
                        current_agent=None, research=research, prd=prd, trd=trd,
                        execution=ExecutionPlan(roadmap="Q1"), pitch=PitchPackage(demo_script="x"))
    backend_id = "run_seed01"
    main_mod._STATES[backend_id] = state
    main_mod._RUNS[backend_id] = {"run_id": backend_id, "idea": state.idea,
                                  "status": "complete", "artifacts": ["research", "prd"]}
    return idmap.alias_for(backend_id)


# --------------------------------------------------------------------------- #
# Envelope + auth
# --------------------------------------------------------------------------- #
def test_login_returns_token_and_user():
    r = client.post("/v1/auth/login", json={"email": "operator@aps.io", "password": "demo1234"})
    body = r.json()
    assert body["success"] is True
    assert set(body["meta"]) >= {"requestId", "timestamp"}
    assert body["data"]["token"] and body["data"]["user"]["email"] == "operator@aps.io"


def test_login_bad_password_error_envelope():
    r = client.post("/v1/auth/login", json={"email": "operator@aps.io", "password": "wrong"})
    assert r.status_code == 401
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_signup_then_login_flow():
    email = "new.operator@aps.io"
    r = client.post("/v1/auth/signup", json={"name": "New Op", "email": email,
                                             "password": "secret12", "role": "Investor"})
    assert r.status_code == 201 and r.json()["data"]["user"]["role"] == "Investor"
    # duplicate → 422 EMAIL_ALREADY_EXISTS
    r2 = client.post("/v1/auth/signup", json={"name": "New Op", "email": email,
                                              "password": "secret12", "role": "Investor"})
    assert r2.status_code == 422 and r2.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    # login with the new account
    r3 = client.post("/v1/auth/login", json={"email": email, "password": "secret12"})
    assert r3.status_code == 200


def test_protected_route_requires_bearer():
    r = client.get("/v1/system/status")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"


def test_signup_validation_error_has_fields():
    r = client.post("/v1/auth/signup", json={"name": "x", "email": "bad", "password": "short",
                                             "role": "Nope"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------- #
# System page — every contract-required key present (§0.8 "never omit a key")
# --------------------------------------------------------------------------- #
def test_system_status_keys(auth):
    d = client.get("/v1/system/status", headers=auth).json()["data"]
    assert set(d) >= {"status", "agentCount", "activeSwarms", "uptimePct", "apiStatus", "version"}


def test_system_health_keys(auth):
    d = client.get("/v1/system/health", headers=auth).json()["data"]
    assert set(d) >= {"agentsActive", "toolsOnline", "memoryLoad", "modelsReady",
                      "evidenceItems", "runsToday", "tokensUsed", "runtimeSec", "uptimePct",
                      "systemVersion", "statusLabel", "activeRunId"}


def test_system_models_shape(auth):
    rows = client.get("/v1/system/models", headers=auth).json()["data"]
    assert len(rows) == 4 and sum(1 for m in rows if m["primary"]) == 1
    for m in rows:
        assert set(m) >= {"id", "name", "provider", "icon", "available", "latencyMs",
                          "tokensM", "costUSD", "successRate", "primary", "color"}


def test_system_observability_20_points(auth):
    d = client.get("/v1/system/observability", headers=auth).json()["data"]
    assert all(len(d[k]) == 20 for k in ("latency", "tokens", "errors", "runs"))


def test_system_heatmap_168_cells(auth):
    d = client.get("/v1/system/activity-heatmap", headers=auth).json()["data"]
    assert len(d["values"]) == 168 and all(0.0 <= v <= 1.0 for v in d["values"])


def test_system_memory_six_layers(auth):
    rows = client.get("/v1/system/memory", headers=auth).json()["data"]
    assert [r["id"] for r in rows] == ["working", "run", "artifact", "evidence", "kg", "longterm"]


def test_mocks_are_deterministic(auth):
    a = client.get("/v1/system/models", headers=auth).json()["data"]
    b = client.get("/v1/system/models", headers=auth).json()["data"]
    assert a == b  # no randomness — stable across calls


def test_telemetry_no_auth_and_grows():
    a = client.get("/v1/system/telemetry/live").json()["data"]
    b = client.get("/v1/system/telemetry/live").json()["data"]
    assert b["memoryIndex"] > a["memoryIndex"]


# --------------------------------------------------------------------------- #
# Dashboard / Artifacts against a seeded run
# --------------------------------------------------------------------------- #
def test_dashboard_run_shape(auth):
    alias = _seed_state()
    d = client.get(f"/v1/runs/{alias}", headers=auth).json()["data"]
    assert set(d) >= {"id", "label", "phase", "progressPct", "startedAt", "elapsedSec",
                      "viabilityScore", "status", "activeAgentId", "systemHealth"}
    assert d["id"] == alias and d["status"] == "complete"
    assert 0 <= d["viabilityScore"] <= 10


def test_run_agents_five_fixed(auth):
    alias = _seed_state()
    rows = client.get(f"/v1/runs/{alias}/agents", headers=auth).json()["data"]
    assert [a["id"] for a in rows] == ["research", "product", "arch", "execution", "present"]


def test_run_artifacts_detail(auth):
    alias = _seed_state()
    rows = client.get(f"/v1/runs/{alias}/artifacts", headers=auth).json()["data"]
    research = next(a for a in rows if a["id"] == "research-brief")
    assert research["status"] == "complete" and research["evidenceCount"] == 2
    assert research["sourceCount"] == 2


def test_run_viability_radar(auth):
    alias = _seed_state()
    d = client.get(f"/v1/runs/{alias}/viability", headers=auth).json()["data"]
    assert len(d["radarAxes"]) == 5 and len(d["scenarios"]) == 3
    assert all(len(s["values"]) == 5 for s in d["scenarios"])


def test_run_debate_sides(auth):
    alias = _seed_state()
    rows = client.get(f"/v1/runs/{alias}/debate", headers=auth).json()["data"]
    assert rows and all(r["side"] in ("Build", "Don't Build") for r in rows)


def test_evidence_graph_edges_reference_nodes(auth):
    alias = _seed_state()
    d = client.get(f"/v1/runs/{alias}/evidence-graph", headers=auth).json()["data"]
    ids = {n["id"] for n in d["nodes"]}
    assert all(a in ids and b in ids for a, b in d["edges"])
    github = next(n for n in d["nodes"] if n["id"] == "github")
    assert github["count"] == 1  # one github evidence in the seed


def test_dna_and_timeline(auth):
    alias = _seed_state()
    dna = client.get(f"/v1/runs/{alias}/dna", headers=auth).json()["data"]
    assert sum(1 for n in dna["nodes"] if n["core"]) == 1
    tl = client.get(f"/v1/runs/{alias}/timeline", headers=auth).json()["data"]
    assert tl[0]["start"] == 0 and tl[-1]["end"] == 100


def test_artifact_content_markdown(auth):
    alias = _seed_state()
    d = client.get("/v1/artifacts/research-brief/content",
                   params={"run": alias}, headers=auth).json()["data"]
    assert d["format"] == "markdown" and "#" in d["body"]


def test_artifact_evidence_traces(auth):
    alias = _seed_state()
    rows = client.get("/v1/artifacts/research-brief/evidence-traces",
                      params={"run": alias}, headers=auth).json()["data"]
    assert rows and rows[0]["sources"]


def test_unknown_run_404(auth):
    r = client.get("/v1/runs/RUN_9999", headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


# --------------------------------------------------------------------------- #
# Run lifecycle (real orchestrator, degrades to stub without keys) + websocket
# --------------------------------------------------------------------------- #
def test_start_run_and_poll(auth):
    r = client.post("/v1/runs", json={"prompt": "a habit tracker for couples"}, headers=auth)
    assert r.status_code == 201
    alias = r.json()["data"]["runId"]
    assert alias.startswith("RUN_")
    # dashboard immediately resolvable (running shell or finished)
    d = client.get(f"/v1/runs/{alias}", headers=auth)
    assert d.status_code == 200 and d.json()["data"]["id"] == alias


def test_websocket_run_stream_seed_and_metric(auth, token):
    alias = _seed_state()
    with client.websocket_connect(f"/v1/ws/runs/{alias}/stream?token={token}") as ws:
        # first frame is either a seeded event or the immediate metric_tick
        first = ws.receive_json()
        assert first["type"] in ("event", "metric_tick")
        # drain until we see a metric_tick (seed has 0 events here, so it's immediate)
        got_metric = first["type"] == "metric_tick"
        for _ in range(3):
            if got_metric:
                break
            msg = ws.receive_json()
            got_metric = msg["type"] == "metric_tick"
        assert got_metric


def test_websocket_rejects_bad_token():
    with client.websocket_connect("/v1/ws/runs/global/stream?token=bogus") as ws:
        # server accepts then closes 1008; the close arrives as a WebSocketDisconnect on receive
        import starlette.websockets
        with pytest.raises(starlette.websockets.WebSocketDisconnect):
            ws.receive_json()
