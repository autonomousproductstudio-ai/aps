"""The /v1 endpoints that were wired from MOCK → REAL backend data.

evidence-graph now shows real pain text + real source→pain edges; system/models lists the
real provider/model catalog with live availability; /v1/models exposes the selector catalog;
and POST /v1/runs accepts a per-run model/provider.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aps.api.main import app
from aps.api import main as main_mod
from aps.api.v1 import idmap
from aps.state.models import (
    StudioState, RunStatus, ResearchReturn, PRD, Competitor, PainPoint, Feature, Evidence, Severity,
)

client = TestClient(app)


@pytest.fixture
def auth():
    r = client.post("/v1/auth/login", json={"email": "operator@aps.io", "password": "demo1234"})
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


def _seed() -> str:
    ev = [Evidence(source="github", url="https://g/1", title="bug",
                   snippet="the resume parser drops valid pdfs"),
          Evidence(source="reddit", url="https://r/2", title="rant",
                   snippet="ranking misses good candidates")]
    research = ResearchReturn(
        idea="AI resume screening", evidence=ev,
        competitors=[Competitor(name="Acme", features=["x"])],
        pain_points=[PainPoint(text="Parser drops valid PDF resumes", severity=Severity.HIGH,
                               source_evidence=ev)])
    prd = PRD(idea="AI resume screening",
              features=[Feature(title="Reliable PDF parsing", description="x", priority="Must")],
              sources=ev)
    st = StudioState(idea="AI resume screening", status=RunStatus.COMPLETE,
                     research=research, prd=prd)
    main_mod._STATES["run_real01"] = st
    main_mod._RUNS["run_real01"] = {"run_id": "run_real01", "idea": st.idea,
                                    "status": "complete", "artifacts": ["research", "prd"]}
    return idmap.alias_for("run_real01")


def test_evidence_graph_uses_real_pain_text_and_edges(auth):
    g = client.get(f"/v1/runs/{_seed()}/evidence-graph", headers=auth).json()["data"]
    pains = [n for n in g["nodes"] if n["type"] == "pain"]
    assert pains and "parser drops valid pdf" in pains[0]["label"].lower()   # REAL pain text
    assert not pains[0]["label"].startswith("Pain #")
    ids = {n["id"] for n in g["nodes"]}
    assert all(a in ids and b in ids for a, b in g["edges"])
    # the pain's github+reddit evidence → real source→pain edges
    assert ["github", "pain1"] in g["edges"] and ["reddit", "pain1"] in g["edges"]
    # the requirement node is labeled from the real PRD feature
    assert any(n["id"] == "req1" and "Reliable" in n["label"] for n in g["nodes"])


def test_system_models_are_real_catalog(auth):
    rows = client.get("/v1/system/models", headers=auth).json()["data"]
    assert len(rows) == 4 and sum(1 for m in rows if m["primary"]) == 1
    provs = {m["provider"] for m in rows}
    assert provs & {"NVIDIA NIM", "Google Gemini"}          # real providers, not Claude/GPT-4o
    assert all(isinstance(m["available"], bool) for m in rows)


def test_v1_models_catalog_endpoint(auth):
    d = client.get("/v1/models", headers=auth).json()["data"]
    assert "providers" in d and "default" in d
    assert d["default"]["provider"] in {"gemini", "nim"}


def test_start_run_accepts_model_and_provider(auth):
    r = client.post("/v1/runs", json={"prompt": "an idea", "provider": "gemini",
                                      "model": "gemini-2.0-flash"}, headers=auth)
    assert r.status_code == 201 and r.json()["data"]["runId"].startswith("RUN_")


def test_explain_why_is_per_feature_with_confidence(auth):
    d = client.get(f"/v1/runs/{_seed()}/explain", headers=auth).json()["data"]
    assert 0 <= d["overallConfidence"] <= 100
    feats = d["features"]
    assert feats and any("Reliable" in f["title"] for f in feats)   # real PRD feature
    f0 = feats[0]
    assert set(f0) >= {"title", "priority", "why", "confidence", "evidence"}
    assert isinstance(f0["confidence"], int) and 0 <= f0["confidence"] <= 100


def test_github_launch_preview_without_token(auth):
    d = client.post(f"/v1/runs/{_seed()}/launch", json={"dryRun": True}, headers=auth).json()["data"]
    assert d["dryRun"] is True and d["created"] is False
    assert d["repoName"] and d["issueCount"] >= 0 and "Preview" in d["message"]


def test_launch_404_when_no_prd(auth):
    main_mod._STATES["run_noprd"] = StudioState(idea="x", status=RunStatus.RUNNING)
    main_mod._RUNS["run_noprd"] = {"run_id": "run_noprd", "idea": "x", "status": "running",
                                   "artifacts": []}
    alias = idmap.alias_for("run_noprd")
    r = client.post(f"/v1/runs/{alias}/launch", json={"dryRun": True}, headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_launch_studio_artifacts_listed_and_render(auth):
    # Brand/Legal/Funding/Availability/Compliance must surface in the /v1 catalog + render.
    from aps.state.models import (BrandPackage, LegalPackage, FundingPackage,
                                  AvailabilityReport, ComplianceReport)
    st = StudioState(idea="AI resume screening", status=RunStatus.COMPLETE,
                     brand=BrandPackage(name="Acme"), legal=LegalPackage(),
                     funding=FundingPackage(), availability=AvailabilityReport(),
                     compliance=ComplianceReport())
    main_mod._STATES["run_ls01"] = st
    main_mod._RUNS["run_ls01"] = {"run_id": "run_ls01", "idea": st.idea,
                                  "status": "complete", "artifacts": []}
    alias = idmap.alias_for("run_ls01")
    rows = client.get(f"/v1/runs/{alias}/artifacts", headers=auth).json()["data"]
    ids = {a["id"]: a for a in rows}
    for aid in ("brand", "legal", "funding", "availability", "compliance"):
        assert aid in ids and ids[aid]["status"] == "complete", f"{aid} missing/not complete"
        assert ids[aid]["agents"]                                  # has a producing-agent label
        body = client.get(f"/v1/artifacts/{aid}/content?run={alias}", headers=auth).json()["data"]
        assert body["format"] == "markdown" and body["body"]       # renders to markdown


def test_disabled_branch_is_not_a_phantom_artifact(auth):
    # compliance is OFF by default — when not produced it must NOT appear as a forever-queued card.
    st = StudioState(idea="x", status=RunStatus.RUNNING)
    main_mod._STATES["run_noLS"] = st
    main_mod._RUNS["run_noLS"] = {"run_id": "run_noLS", "idea": "x", "status": "running",
                                  "artifacts": []}
    alias = idmap.alias_for("run_noLS")
    ids = {a["id"] for a in client.get(f"/v1/runs/{alias}/artifacts", headers=auth).json()["data"]}
    assert "compliance" not in ids                                 # disabled + absent → not shown


def test_system_providers_is_real_failover_chain(auth):
    d = client.get("/v1/system/providers", headers=auth).json()["data"]
    assert isinstance(d["chain"], list) and d["chain"]                 # ordered failover path
    names = {p["name"] for p in d["registry"]}
    assert {"gemini", "nim", "groq"} <= names                          # real registry, not GPT-4o
    p0 = d["chain"][0]
    assert p0["primary"] is True
    assert set(p0) >= {"name", "model", "available", "breakerOpen", "signup"}
    assert all(isinstance(p["available"], bool) and isinstance(p["breakerOpen"], bool)
               for p in d["registry"])


def test_trd_mermaid_artifact_content(auth):
    from aps.state.models import TRD
    trd = TRD(stack=["FastAPI", "Postgres"],
              data_model={"architecture": {"components": ["API Gateway", "Worker"],
                                           "data_flow": ["API Gateway -> Worker"]},
                          "entities": {"User": {"fields": {"id": "int", "email": "str"}}}})
    st = StudioState(idea="AI resume screening", status=RunStatus.COMPLETE, trd=trd)
    main_mod._STATES["run_trd01"] = st
    main_mod._RUNS["run_trd01"] = {"run_id": "run_trd01", "idea": st.idea,
                                   "status": "complete", "artifacts": ["trd"]}
    alias = idmap.alias_for("run_trd01")
    d = client.get(f"/v1/artifacts/trd/content?run={alias}&format=mermaid",
                   headers=auth).json()["data"]
    assert d["format"] == "mermaid" and "```mermaid" in d["body"]
